"""Command line entry point and the single-repository pipeline."""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

import pandas as pd

from . import __version__, plots
from .features import FeatureOptions, build_features, filter_authors
from .fetch import GitHubGraphQL, GraphQLClient, fetch_file_lists, fetch_pull_requests
from .filetypes import file_check, select_sample, summarise_files
from .report import write_report, write_results_json
from .stats import (
    exposure_effects,
    label_table,
    monthly_table,
    size_label_check,
    tool_robustness,
    verdict,
    trend_test,
    window_numeric_table,
    window_proportion_table,
)
from .text import summarise_template_changes

DEFAULT_START = date(2025, 1, 6)
DEFAULT_END = date(2026, 8, 17)
EXPOSURES = ("ai_disclosed",)
TREND_COLUMNS = [
    "median_words", "median_files_changed", "median_additions", "median_deletions", "median_churn",
    "median_hours_to_merge", "merge_rate", "share_outside_contributors", "share_ai_disclosed",
    "median_comments", "median_reviews",
]

log = logging.getLogger("prwords")


def analyse_repo(
    client: GraphQLClient, repo: str, start: date, end: date, out_dir: Path, cache_dir: Path,
    args: argparse.Namespace,
) -> dict:
    owner, name = repo.split("/", 1)
    raw, fetched_at, language = fetch_pull_requests(
        client, owner, name, start, end, cache_dir, args.page_size, args.with_commit_messages
    )
    if raw.empty:
        raise SystemExit(f"No pull requests found for {repo} in the window.")

    kept = filter_authors(raw, args.author_weekly_cap)
    n_bots_and_cap = len(raw) - len(kept)
    n_bots = len(raw) - len(filter_authors(raw, None))
    opts = FeatureOptions(
        author_weekly_cap=args.author_weekly_cap, template_share=args.template_share,
        template_min_docs=args.template_min_docs, followup_days=args.followup_days,
        label_map=args.label_map, language=language,
    )
    feat, audit, clf = build_features(kept, fetched_at, opts)
    cat_cols = [f"cat_{c}" for c in clf.categories]
    cat_names = clf.categories

    repo_dir = out_dir / f"{owner}__{name}"
    repo_dir.mkdir(parents=True, exist_ok=True)

    # Tables
    feat.drop(columns=["body", "ai_commit_match"], errors="ignore").assign(
        labels=feat["labels"].map("|".join)
    ).to_csv(repo_dir / "pr_features.csv", index=False)
    templates = summarise_template_changes(audit)
    audit.to_csv(repo_dir / "template_audit.csv", index=False)
    templates.to_csv(repo_dir / "template_lines_summary.csv", index=False)

    monthly = monthly_table(feat, start, end, cat_cols, args.n_boot)
    monthly.to_csv(repo_dir / "monthly_summary.csv", index=False)
    win_num = window_numeric_table(feat, start, end, args.window_days, args.n_boot)
    win_prop = window_proportion_table(feat, start, end, cat_cols, args.window_days)
    win_num.to_csv(repo_dir / "window_numeric.csv", index=False)
    win_prop.to_csv(repo_dir / "window_proportions.csv", index=False)
    trends = [trend_test(monthly, c) for c in TREND_COLUMNS + [f"share_{c}" for c in cat_names]]
    labels = label_table(feat, cat_cols)
    labels.to_csv(repo_dir / "label_summary.csv", index=False)
    size_check = size_label_check(feat)

    effects = pd.concat(
        [exposure_effects(feat, e, args.min_exposed, args.n_perm) for e in EXPOSURES], ignore_index=True
    )
    effects.to_csv(repo_dir / "exposure_effects.csv", index=False)
    verdicts = {e: verdict(effects[effects["exposure"] == e]) for e in EXPOSURES}
    tools = tool_robustness(feat, args.min_exposed, max(args.n_perm // 10, 50))
    tools.to_csv(repo_dir / "tool_robustness.csv", index=False)

    file_res = None
    if args.file_check > 0 and feat["ai_disclosed"].sum() >= args.min_exposed:
        numbers = select_sample(feat, args.file_check)
        files = fetch_file_lists(client, owner, name, numbers, cache_dir)
        file_res = file_check(feat, files, args.min_exposed)
        summarise_files(files).to_csv(repo_dir / "file_type_sample.csv", index=False)
        file_res["mix"].to_csv(repo_dir / "file_type_mix.csv", index=False)

    samples = feat[feat["ai_disclosed"]].sample(min(50, int(feat["ai_disclosed"].sum())), random_state=42) \
        if feat["ai_disclosed"].any() else feat.head(0)
    samples[["number", "created_at", "author", "ai_tool", "ai_match"]].to_csv(
        repo_dir / "ai_disclosure_samples.csv", index=False)

    # Charts
    if not args.no_plots:
        plots.plot_words(monthly, repo, repo_dir / "words_monthly.png")
        plots.plot_size(monthly, repo, repo_dir / "size_monthly.png")
        plots.plot_flow(monthly, repo, repo_dir / "flow_monthly.png")
        plots.plot_labels(monthly, cat_names, repo, repo_dir / "labels_monthly.png")
        plots.plot_ai_signals(monthly, repo, repo_dir / "ai_signals_monthly.png")
        if (effects["status"] == "ok").any():
            plots.plot_effects(effects, repo, repo_dir / "effects.png")

    ctx = dict(repo=repo, start=start, end=end, fetched_at=fetched_at, args=args, language=language,
               n_fetched=len(raw), n_bots=n_bots, n_capped=n_bots_and_cap - n_bots, feat=feat, monthly=monthly,
               win_num=win_num, win_prop=win_prop, trends=trends, labels=labels, size_check=size_check,
               templates=templates, effects=effects, verdicts=verdicts, tools=tools, file_res=file_res,
               ai_samples_n=len(samples))
    write_report(repo_dir / "report.md", ctx)
    write_results_json(repo_dir / "results.json", ctx)
    log.info("Wrote results to %s", repo_dir)
    return {"repo": repo, "dir": repo_dir, "features": feat, "monthly": monthly, "effects": effects,
            "window_numeric": win_num, "templates": templates, "verdicts": verdicts, "tools": tools,
            "file_check": file_res, "language": language}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="prwords", description=__doc__)
    p.add_argument("repo", help="owner/name, for example kubernetes/kubernetes")
    p.add_argument("--start", type=date.fromisoformat, default=DEFAULT_START)
    p.add_argument("--end", type=date.fromisoformat, default=DEFAULT_END)
    p.add_argument("--out", type=Path, default=Path("results"))
    p.add_argument("--cache", type=Path, default=Path("cache"))
    p.add_argument("--page-size", type=int, default=50, help="PRs per API request, halved automatically on timeouts")
    p.add_argument("--with-commit-messages", action="store_true",
                   help="also scan commit messages for AI co-author lines (slower, heavier API use)")
    p.add_argument("--author-weekly-cap", type=int, default=None,
                   help="keep at most N PRs per author per ISO week (the source study used 3)")
    p.add_argument("--template-share", type=float, default=0.20)
    p.add_argument("--template-min-docs", type=int, default=30)
    p.add_argument("--followup-days", type=int, default=30)
    p.add_argument("--window-days", type=int, default=28)
    p.add_argument("--label-map", type=Path, default=None, help="JSON file {category: [regex, ...]}")
    p.add_argument("--min-exposed", type=int, default=30)
    p.add_argument("--file-check", type=int, default=300,
                   help="sample up to N exposed PRs (plus matching others) for the file type check, 0 to skip")
    p.add_argument("--n-boot", type=int, default=1000)
    p.add_argument("--n-perm", type=int, default=2000)
    p.add_argument("--no-plots", action="store_true")
    p.add_argument("--version", action="version", version=f"prwords {__version__}")
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    if "/" not in args.repo:
        raise SystemExit("repo must look like owner/name")
    if args.start >= args.end:
        raise SystemExit("--start must be before --end")
    res = analyse_repo(GitHubGraphQL(), args.repo, args.start, args.end, args.out, args.cache, args)
    for exp, v in res["verdicts"].items():
        print(f"{exp}: {v.category}. {v.pattern}")
    print(f"Report: {res['dir'] / 'report.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
