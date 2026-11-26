#!/usr/bin/env python3
"""prwords: how long are pull request descriptions, and has that changed over time?

For one GitHub repository, this tool collects every pull request opened in a
time window, measures the number of words in each description, and reports how
the distribution moves month by month.

Pipeline
    1. fetch    GitHub GraphQL API, newest first, resumable JSONL cache
    2. filter   drop bots, optionally cap PRs per author per week
    3. clean    strip comments, code, URLs, images, HTML and repeated template lines
    4. measure  words_raw (everything) and words_prose (cleaned), per PR
    5. summarise  monthly statistics with bootstrap confidence intervals
    6. test     first window versus last window, plus a monotonic trend test
    7. report   CSV, PNG chart and a Markdown report

Usage
    export GH_TOKEN=...            # a token with public repo read access
    python prwords.py kubernetes/kubernetes
    python prwords.py apache/spark --start 2025-01-06 --end 2026-08-17

The default window matches the study that motivated this work
(2025-01-06 to 2026-08-17).
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Protocol

import numpy as np
import pandas as pd
import requests
from scipy import stats

__version__ = "1.0.0"
log = logging.getLogger("prwords")

DEFAULT_START = date(2025, 1, 6)
DEFAULT_END = date(2026, 8, 17)
GRAPHQL_URL = "https://api.github.com/graphql"

PR_QUERY = """
query($owner: String!, $name: String!, $cursor: String) {
  rateLimit { remaining resetAt cost }
  repository(owner: $owner, name: $name) {
    pullRequests(first: 100, after: $cursor,
                 orderBy: {field: CREATED_AT, direction: DESC}) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number
        createdAt
        body
        isDraft
        authorAssociation
        author { login __typename }
      }
    }
  }
}
"""


# --------------------------------------------------------------------------- #
# Fetching
# --------------------------------------------------------------------------- #
class GraphQLClient(Protocol):
    def graphql(self, query: str, variables: dict) -> dict: ...


class GitHubGraphQL:
    """Minimal GitHub GraphQL client with retry and rate limit handling."""

    def __init__(self, token: str | None = None, max_retries: int = 6) -> None:
        token = token or os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if not token:
            raise SystemExit("Set GH_TOKEN or GITHUB_TOKEN to a GitHub access token.")
        self.session = requests.Session()
        self.session.headers.update(
            {"Authorization": f"bearer {token}", "User-Agent": f"prwords/{__version__}"}
        )
        self.max_retries = max_retries

    def graphql(self, query: str, variables: dict) -> dict:
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.session.post(
                    GRAPHQL_URL, json={"query": query, "variables": variables}, timeout=60
                )
            except requests.RequestException as exc:
                self._backoff(attempt, f"network error: {exc}")
                continue
            if resp.status_code in (502, 503, 504):
                self._backoff(attempt, f"HTTP {resp.status_code}")
                continue
            if resp.status_code in (403, 429) and "retry-after" in resp.headers:
                time.sleep(int(resp.headers["retry-after"]) + 1)
                continue
            resp.raise_for_status()
            payload = resp.json()
            if "errors" in payload and not payload.get("data"):
                raise RuntimeError(f"GraphQL error: {payload['errors']}")
            self._respect_rate_limit(payload.get("data") or {})
            return payload["data"]
        raise RuntimeError("GitHub API kept failing after retries")

    @staticmethod
    def _backoff(attempt: int, why: str) -> None:
        delay = min(2 ** attempt, 60)
        log.warning("%s, retrying in %ss", why, delay)
        time.sleep(delay)

    @staticmethod
    def _respect_rate_limit(data: dict) -> None:
        rl = data.get("rateLimit")
        if rl and rl["remaining"] < 25:
            reset = datetime.fromisoformat(rl["resetAt"].replace("Z", "+00:00"))
            wait = max((reset - datetime.now(timezone.utc)).total_seconds(), 0) + 5
            log.info("Rate limit nearly exhausted, sleeping %.0fs", wait)
            time.sleep(wait)


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def fetch_pull_requests(
    client: GraphQLClient,
    owner: str,
    name: str,
    start: date,
    end: date,
    cache_dir: Path,
) -> pd.DataFrame:
    """Return all PRs created in [start, end] (UTC, inclusive) as a DataFrame.

    Pages newest first and stops once it passes `start`. Progress is written to
    `<cache_dir>/<owner>__<name>.jsonl` with a sidecar state file, so an
    interrupted run resumes from the last completed page.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{owner}__{name}"
    data_path = cache_dir / f"{stem}.jsonl"
    state_path = cache_dir / f"{stem}.state.json"
    window = {"start": start.isoformat(), "end": end.isoformat()}

    state = {"cursor": None, "done": False, "window": window}
    if state_path.exists() and data_path.exists():
        saved = json.loads(state_path.read_text())
        if saved.get("window") == window:
            state = saved
            log.info("Resuming %s (done=%s)", stem, state["done"])
        else:
            log.info("Window changed, discarding cache for %s", stem)
            data_path.unlink()

    lo = datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc)
    hi = datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)

    if not state["done"]:
        pages = 0
        with data_path.open("a", encoding="utf-8") as fh:
            while True:
                data = client.graphql(
                    PR_QUERY, {"owner": owner, "name": name, "cursor": state["cursor"]}
                )
                conn = data["repository"]["pullRequests"]
                reached_start = False
                for node in conn["nodes"]:
                    created = _parse_ts(node["createdAt"])
                    if created < lo:
                        reached_start = True
                        continue
                    if created >= hi:
                        continue
                    author = node.get("author") or {}
                    fh.write(
                        json.dumps(
                            {
                                "number": node["number"],
                                "created_at": node["createdAt"],
                                "body": node.get("body") or "",
                                "is_draft": node.get("isDraft", False),
                                "association": node.get("authorAssociation"),
                                "author": author.get("login") or "ghost",
                                "author_type": author.get("__typename") or "User",
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
                fh.flush()
                pages += 1
                state["cursor"] = conn["pageInfo"]["endCursor"]
                state["done"] = reached_start or not conn["pageInfo"]["hasNextPage"]
                state_path.write_text(json.dumps(state))
                if pages % 20 == 0:
                    log.info("%s: %d pages fetched", stem, pages)
                if state["done"]:
                    break

    rows = [json.loads(line) for line in data_path.read_text(encoding="utf-8").splitlines()]
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["created_at"] = pd.to_datetime(df["created_at"], utc=True)
    return df.drop_duplicates("number").sort_values("created_at").reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Filtering
# --------------------------------------------------------------------------- #
_BOT_NAME = re.compile(r"(\[bot\]$|-bot$|^copilot$|^dependabot|^renovate)", re.I)


def is_bot(login: str, author_type: str) -> bool:
    return author_type == "Bot" or bool(_BOT_NAME.search(login or ""))


def filter_authors(df: pd.DataFrame, weekly_cap: int | None = None) -> pd.DataFrame:
    """Remove bot accounts and optionally cap PRs per author per ISO week."""
    keep = ~df.apply(lambda r: is_bot(r["author"], r["author_type"]), axis=1)
    out = df[keep].copy()
    if weekly_cap:
        week = out["created_at"].dt.strftime("%G-W%V")
        rank = out.groupby([out["author"], week]).cumcount()
        out = out[rank < weekly_cap]
    return out.reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Text cleaning and counting
# --------------------------------------------------------------------------- #
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
_FENCED = re.compile(r"(```|~~~).*?\1", re.S)
_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_URL = re.compile(r"https?://\S+")
_HTML_TAG = re.compile(r"<[^>]+>")
_LIST_MARKER = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s*(?:\[[ xX]\]\s*)?")
_WORD = re.compile(r"[^\W_]+(?:['’\-][^\W_]+)*", re.UNICODE)


def count_words(text: str) -> int:
    """Count word tokens: letters/digits with internal apostrophes or hyphens."""
    return len(_WORD.findall(text))


def strip_markup(text: str) -> str:
    """Remove content that is not prose: comments, code fences, images, URLs, tags."""
    text = _HTML_COMMENT.sub(" ", text)
    text = _FENCED.sub(" ", text)
    text = _IMAGE.sub(" ", text)
    text = _LINK.sub(r"\1", text)
    text = _URL.sub(" ", text)
    return _HTML_TAG.sub(" ", text)


def _normalise_line(line: str) -> str:
    line = _LIST_MARKER.sub("", line.strip().lower())
    return re.sub(r"\s+", " ", line)


def detect_template_lines(
    bodies: Iterable[str], min_share: float = 0.20, min_docs: int = 30
) -> set[str]:
    """Find lines that recur across a large share of PR bodies (template text).

    A normalised line (lowercase, list markers and checkbox state removed) is
    classed as template when it appears in at least `min_share` of the bodies
    and at least `min_docs` bodies. Returns an empty set for small samples.
    """
    bodies = list(bodies)
    n = len(bodies)
    if n < min_docs:
        return set()
    seen: Counter[str] = Counter()
    for body in bodies:
        lines = {_normalise_line(l) for l in strip_markup_keep_lines(body).splitlines()}
        seen.update(l for l in lines if l)
    threshold = max(min_docs, int(np.ceil(min_share * n)))
    return {line for line, c in seen.items() if c >= threshold}


def strip_markup_keep_lines(text: str) -> str:
    """Like strip_markup, but keeps line structure so lines can be compared."""
    text = _HTML_COMMENT.sub("\n", text)
    text = _FENCED.sub("\n", text)
    text = _IMAGE.sub(" ", text)
    text = _LINK.sub(r"\1", text)
    text = _URL.sub(" ", text)
    return _HTML_TAG.sub(" ", text)


def prose_words(body: str, template_lines: set[str]) -> int:
    """Words left after removing markup and template lines."""
    kept = [
        line
        for line in strip_markup_keep_lines(body).splitlines()
        if _normalise_line(line) not in template_lines
    ]
    return count_words("\n".join(kept))


def add_word_counts(
    df: pd.DataFrame, template_share: float = 0.20, template_min_docs: int = 30
) -> pd.DataFrame:
    """Add words_raw and words_prose. Template lines are detected per quarter so
    a template that changes over time is handled correctly."""
    out = df.copy()
    out["words_raw"] = out["body"].map(count_words)
    out["quarter"] = out["created_at"].dt.tz_convert(None).dt.to_period("Q").astype(str)
    prose = pd.Series(0, index=out.index, dtype="int64")
    for _, idx in out.groupby("quarter").groups.items():
        bodies = out.loc[idx, "body"]
        template = detect_template_lines(bodies, template_share, template_min_docs)
        prose.loc[idx] = [prose_words(b, template) for b in bodies]
    out["words_prose"] = prose
    return out


# --------------------------------------------------------------------------- #
# Statistics
# --------------------------------------------------------------------------- #
def _bootstrap_median_ci(
    values: np.ndarray, rng: np.random.Generator, n_boot: int = 2000
) -> tuple[float, float]:
    if len(values) < 5:
        return (np.nan, np.nan)
    draws = rng.choice(values, size=(n_boot, len(values)), replace=True)
    lo, hi = np.percentile(np.median(draws, axis=1), [2.5, 97.5])
    return float(lo), float(hi)


def monthly_summary(df: pd.DataFrame, metric: str = "words_prose", seed: int = 42) -> pd.DataFrame:
    """Per calendar month: counts, share of empty descriptions, and word statistics.

    Word statistics (mean, median, quartiles, p90) use non-empty descriptions.
    `mean_all` treats empty descriptions as zero words.
    """
    rng = np.random.default_rng(seed)
    month = df["created_at"].dt.tz_convert(None).dt.to_period("M")
    rows = []
    for period, g in df.groupby(month):
        vals = g[metric].to_numpy()
        nonempty = vals[vals > 0]
        lo, hi = _bootstrap_median_ci(nonempty, rng)
        q = np.percentile(nonempty, [25, 75, 90]) if len(nonempty) else [np.nan] * 3
        rows.append(
            {
                "month": str(period),
                "n_prs": len(g),
                "n_authors": g["author"].nunique(),
                "share_empty": float((vals == 0).mean()),
                "mean_all": float(vals.mean()),
                "mean_words": float(nonempty.mean()) if len(nonempty) else np.nan,
                "median_words": float(np.median(nonempty)) if len(nonempty) else np.nan,
                "median_ci_low": lo,
                "median_ci_high": hi,
                "p25": float(q[0]),
                "p75": float(q[1]),
                "p90": float(q[2]),
            }
        )
    return pd.DataFrame(rows)


@dataclass
class WindowComparison:
    baseline_start: date
    baseline_end: date
    final_start: date
    final_end: date
    n_baseline: int
    n_final: int
    median_baseline: float
    median_final: float
    ratio: float
    ratio_ci_low: float
    ratio_ci_high: float
    mannwhitney_p: float
    cliffs_delta: float


def compare_windows(
    df: pd.DataFrame,
    start: date,
    end: date,
    days: int = 28,
    metric: str = "words_prose",
    seed: int = 42,
    n_boot: int = 2000,
) -> WindowComparison:
    """Compare the first and last `days` of the window (default: four weeks, as in
    the source study). Uses non-empty descriptions."""
    rng = np.random.default_rng(seed)
    ts = df["created_at"].dt.tz_convert(None).dt.date

    b_end = start + timedelta(days=days - 1)
    f_start = end - timedelta(days=days - 1)
    base = df.loc[(ts >= start) & (ts <= b_end), metric].to_numpy()
    fin = df.loc[(ts >= f_start) & (ts <= end), metric].to_numpy()
    base, fin = base[base > 0], fin[fin > 0]
    if len(base) < 5 or len(fin) < 5:
        raise ValueError(
            f"Too few non-empty descriptions in a comparison window "
            f"(baseline={len(base)}, final={len(fin)})."
        )

    med_b, med_f = float(np.median(base)), float(np.median(fin))
    boot_b = np.median(rng.choice(base, (n_boot, len(base))), axis=1)
    boot_f = np.median(rng.choice(fin, (n_boot, len(fin))), axis=1)
    ratio_draws = boot_f / boot_b
    lo, hi = np.percentile(ratio_draws, [2.5, 97.5])
    u = stats.mannwhitneyu(fin, base, alternative="two-sided")
    cliffs = 2 * u.statistic / (len(fin) * len(base)) - 1
    return WindowComparison(
        start, b_end, f_start, end, len(base), len(fin), med_b, med_f,
        med_f / med_b, float(lo), float(hi), float(u.pvalue), float(cliffs),
    )


def trend_test(monthly: pd.DataFrame) -> dict:
    """Theil-Sen slope and Kendall tau for monthly median words against time."""
    m = monthly.dropna(subset=["median_words"])
    if len(m) < 6:
        return {"months": len(m), "slope_per_month": np.nan, "tau": np.nan, "p": np.nan}
    x = np.arange(len(m))
    slope, intercept, lo, hi = stats.theilslopes(m["median_words"], x)
    tau, p = stats.kendalltau(x, m["median_words"])
    return {
        "months": len(m),
        "slope_per_month": float(slope),
        "slope_ci_low": float(lo),
        "slope_ci_high": float(hi),
        "tau": float(tau),
        "p": float(p),
    }


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
INK = "#1f2933"
MUTED = "#6b7785"
GRID = "#e4e7eb"
LINE = "#2f6db5"
BAND = "#2f6db5"


def plot_monthly(monthly: pd.DataFrame, repo: str, path: Path, metric_label: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    x = pd.to_datetime(monthly["month"]) + pd.Timedelta(days=14)
    fig, (ax, ax2) = plt.subplots(
        2, 1, figsize=(10, 6.2), sharex=True, gridspec_kw={"height_ratios": [3.2, 1], "hspace": 0.08}
    )
    ax.fill_between(x, monthly["p25"], monthly["p75"], color=BAND, alpha=0.14, linewidth=0,
                    label="Middle 50% of PRs")
    ax.fill_between(x, monthly["median_ci_low"], monthly["median_ci_high"], color=BAND,
                    alpha=0.30, linewidth=0, label="95% interval for median")
    ax.plot(x, monthly["median_words"], color=LINE, linewidth=2, marker="o", markersize=5,
            markeredgecolor="white", markeredgewidth=1.5, label="Median")
    ax.set_ylabel(f"Words per description\n({metric_label})", color=INK)
    ax.set_title(f"{repo}: pull request description length by month", loc="left",
                 color=INK, fontsize=13, fontweight="bold")
    ax.legend(frameon=False, loc="upper left", labelcolor=MUTED, fontsize=9)

    ax2.bar(x, monthly["n_prs"], width=20, color=MUTED, alpha=0.55)
    ax2.set_ylabel("PRs opened", color=INK)

    for a in (ax, ax2):
        a.set_axisbelow(True)
        a.grid(axis="y", color=GRID, linewidth=0.8)
        for side in ("top", "right", "left"):
            a.spines[side].set_visible(False)
        a.spines["bottom"].set_color(GRID)
        a.tick_params(colors=MUTED, length=0)
    ax.set_ylim(bottom=0)
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def write_report(
    path: Path,
    repo: str,
    start: date,
    end: date,
    raw: pd.DataFrame,
    kept: pd.DataFrame,
    monthly: pd.DataFrame,
    cmp_: WindowComparison | None,
    trend: dict,
    args: argparse.Namespace,
) -> None:
    lines = [
        f"# PR description length: {repo}",
        "",
        f"Window: {start} to {end} (UTC). Generated by prwords {__version__} on "
        f"{datetime.now(timezone.utc):%Y-%m-%d}.",
        "",
        "## Data",
        "",
        f"- Pull requests fetched: {len(raw):,}",
        f"- After removing bots{' and applying the weekly author cap' if args.author_weekly_cap else ''}: {len(kept):,}",
        f"- Empty descriptions (prose words = 0): {(kept['words_prose'] == 0).mean():.1%}",
        f"- Metric: `words_prose`, words left after removing HTML comments, code blocks, images, "
        f"URLs, HTML tags and template lines (lines present in at least "
        f"{args.template_share:.0%} of a quarter's descriptions).",
        "",
        "## First four weeks versus last four weeks",
        "",
    ]
    if cmp_:
        lines += [
            "| | Baseline | Final |",
            "|---|---|---|",
            f"| Dates | {cmp_.baseline_start} to {cmp_.baseline_end} | {cmp_.final_start} to {cmp_.final_end} |",
            f"| Non-empty PRs | {cmp_.n_baseline:,} | {cmp_.n_final:,} |",
            f"| Median words | {cmp_.median_baseline:.1f} | {cmp_.median_final:.1f} |",
            "",
            f"Median ratio (final / baseline): **{cmp_.ratio:.2f}** "
            f"(95% bootstrap interval {cmp_.ratio_ci_low:.2f} to {cmp_.ratio_ci_high:.2f}). "
            f"Mann-Whitney p = {cmp_.mannwhitney_p:.2g}; Cliff's delta = {cmp_.cliffs_delta:+.2f}.",
        ]
    else:
        lines.append("Not enough non-empty descriptions in one of the two windows.")
    lines += ["", "## Monthly trend", ""]
    if not np.isnan(trend.get("slope_per_month", np.nan)):
        lines.append(
            f"Theil-Sen slope of the monthly median: {trend['slope_per_month']:+.2f} words per month "
            f"(95% interval {trend['slope_ci_low']:+.2f} to {trend['slope_ci_high']:+.2f}), "
            f"Kendall tau = {trend['tau']:+.2f}, p = {trend['p']:.2g}, over {trend['months']} months."
        )
    else:
        lines.append("Fewer than six months of data, no trend fitted.")
    table = monthly[["month", "n_prs", "share_empty", "median_words", "p25", "p75", "p90", "mean_words"]].copy()
    table["share_empty"] = (table["share_empty"] * 100).round(1).astype(str) + "%"
    lines += [
        "",
        "![Monthly median](monthly_median.png)",
        "",
        "## Monthly statistics",
        "",
        table.round(1).to_markdown(index=False),
        "",
        "## Limitations",
        "",
        "- Word count measures length only. It says nothing about who or what wrote a description.",
        "- Length shifts can come from template changes, policy changes, a new contributor mix or "
        "changes in what the project accepts. Template removal is heuristic.",
        "- Months with few PRs have wide intervals. Read the interval, not only the line.",
        "- Bot filtering relies on account type and name patterns and will miss some automation.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def analyse_repo(
    client: GraphQLClient,
    repo: str,
    start: date,
    end: date,
    out_dir: Path,
    cache_dir: Path,
    args: argparse.Namespace,
) -> dict:
    owner, name = repo.split("/", 1)
    raw = fetch_pull_requests(client, owner, name, start, end, cache_dir)
    if raw.empty:
        raise SystemExit(f"No pull requests found for {repo} in the window.")
    kept = filter_authors(raw, args.author_weekly_cap)
    kept = add_word_counts(kept, args.template_share, args.template_min_docs)

    repo_dir = out_dir / f"{owner}__{name}"
    repo_dir.mkdir(parents=True, exist_ok=True)
    kept.drop(columns=["body"]).to_csv(repo_dir / "pr_word_counts.csv", index=False)

    monthly = monthly_summary(kept)
    monthly.to_csv(repo_dir / "monthly_summary.csv", index=False)
    plot_monthly(monthly, repo, repo_dir / "monthly_median.png", "prose words, empty excluded")

    try:
        cmp_ = compare_windows(kept, start, end)
    except ValueError as exc:
        log.warning("%s", exc)
        cmp_ = None
    trend = trend_test(monthly)
    write_report(repo_dir / "report.md", repo, start, end, raw, kept, monthly, cmp_, trend, args)
    log.info("Wrote results to %s", repo_dir)
    return {"repo": repo, "n_raw": len(raw), "n_kept": len(kept), "comparison": cmp_, "trend": trend}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("repo", help="owner/name, for example kubernetes/kubernetes")
    p.add_argument("--start", type=date.fromisoformat, default=DEFAULT_START)
    p.add_argument("--end", type=date.fromisoformat, default=DEFAULT_END)
    p.add_argument("--out", type=Path, default=Path("results"))
    p.add_argument("--cache", type=Path, default=Path("cache"))
    p.add_argument("--author-weekly-cap", type=int, default=None,
                   help="keep at most N PRs per author per ISO week (the source study used 3)")
    p.add_argument("--template-share", type=float, default=0.20,
                   help="a line is template text if it appears in this share of a quarter's PRs")
    p.add_argument("--template-min-docs", type=int, default=30)
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
    result = analyse_repo(GitHubGraphQL(), args.repo, args.start, args.end, args.out, args.cache, args)
    c = result["comparison"]
    if c:
        print(f"{args.repo}: median {c.median_baseline:.0f} -> {c.median_final:.0f} words "
              f"(x{c.ratio:.2f}, 95% CI {c.ratio_ci_low:.2f} to {c.ratio_ci_high:.2f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
