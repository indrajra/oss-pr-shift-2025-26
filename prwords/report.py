"""Markdown and JSON report assembly. Numbers and the pre-specified verdict, nothing beyond them."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from . import __version__
from .stats import Verdict


def _fmt(x, nd=1, pct=False) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "n/a"
    return f"{x:.{nd}%}" if pct else f"{x:,.{nd}f}"


def _md(df: pd.DataFrame, nd: int = 1) -> str:
    return df.round(nd).to_markdown(index=False)


def _window_numeric_md(w: pd.DataFrame) -> str:
    cols = ["label", "n_baseline", "n_final", "median_baseline", "median_final", "ratio",
            "ratio_ci_low", "ratio_ci_high", "mannwhitney_p", "cliffs_delta"]
    t = w.reindex(columns=cols).copy()
    t["mannwhitney_p"] = t["mannwhitney_p"].map(lambda v: "n/a" if pd.isna(v) else f"{v:.2g}")
    return t.rename(columns={
        "label": "Metric", "n_baseline": "n first", "n_final": "n last", "median_baseline": "Median first",
        "median_final": "Median last", "ratio": "Ratio", "ratio_ci_low": "Ratio low", "ratio_ci_high": "Ratio high",
        "mannwhitney_p": "p", "cliffs_delta": "Cliff's delta",
    }).round(2).to_markdown(index=False)


def _window_prop_md(w: pd.DataFrame) -> str:
    t = w.copy()
    for c in ("share_baseline", "share_final"):
        t[c] = t[c].map(lambda v: "n/a" if pd.isna(v) else f"{v:.1%}")
    t["fisher_p"] = t["fisher_p"].map(lambda v: "n/a" if pd.isna(v) else f"{v:.2g}")
    t["change_points"] = t["change_points"].round(1)
    cols = ["label", "n_baseline", "n_final", "share_baseline", "share_final", "change_points", "fisher_p"]
    return t[cols].rename(columns={
        "label": "Measure", "n_baseline": "n first", "n_final": "n last", "share_baseline": "Share first",
        "share_final": "Share last", "change_points": "Change (points)", "fisher_p": "p"}).to_markdown(index=False)


def _effects_md(e: pd.DataFrame, exposure: str) -> str:
    sub = e[e["exposure"] == exposure]
    if sub.empty:
        return "No results."
    if (sub["status"] != "ok").all():
        return f"Not estimated: {sub.iloc[0]['status']} (exposed PRs: {int(sub.iloc[0]['n_exposed'])})."
    ok = sub[sub["status"] == "ok"].copy()
    ok["effect"] = ok.apply(lambda r: f"{r['pct_difference']:+.1f}% ({r['ci_low']:+.1f} to {r['ci_high']:+.1f})", axis=1)
    ok["p"] = ok["p"].map(lambda v: f"{v:.2g}")
    ok["p_holm"] = ok["p_holm"].map(lambda v: f"{v:.2g}")
    t = ok[["label", "model", "n", "n_exposed", "median_exposed", "median_unexposed", "effect", "p", "p_holm"]]
    return t.rename(columns={
        "label": "Outcome", "model": "Model", "n_exposed": "n exposed", "median_exposed": "Median exposed",
        "median_unexposed": "Median others", "effect": "Difference (95% CI)", "p_holm": "p (Holm)"}).round(1).to_markdown(index=False)


def _tools_md(t: pd.DataFrame) -> str:
    if t is None or t.empty:
        return "No tool named in any disclosure."
    t = t.copy()
    for tag in ("m1", "m3"):
        if f"{tag}_pct" in t:
            t[tag] = t.apply(lambda r: "n/a" if pd.isna(r.get(f"{tag}_pct")) else
                             f"{r[f'{tag}_pct']:+.1f}% ({r[f'{tag}_low']:+.1f} to {r[f'{tag}_high']:+.1f})", axis=1)
    cols = [c for c in ("tool", "n_exposed", "m1", "m3", "call", "status") if c in t]
    return t[cols].rename(columns={"m1": "Same month", "m3": "Same author", "n_exposed": "n exposed"}).to_markdown(index=False)


def _file_md(res: dict | None) -> list[str]:
    if res is None:
        return ["Not run. Use `--file-check N` to sample N exposed PRs and matching unexposed PRs.", ""]
    mix = res["mix"].copy()
    for c in mix.columns:
        if c not in ("group", "n_prs", "median_code_test_lines"):
            mix[c] = (mix[c] * 100).round(1).astype(str) + "%"
    out = [f"Sample: {res['n_exposed']} exposed and {res['n_unexposed']} unexposed PRs from the same months. "
           f"{res['n_truncated_excluded']} PRs with more than 100 files were excluded.", "",
           "Share of changed lines by file type:", "", mix.round(1).to_markdown(index=False), ""]
    eff = res.get("effect")
    if eff is None:
        out += [f"Code and test lines: not estimated ({res['status']}).", ""]
    else:
        out += [f"Code and test lines only, same month: {eff.pct:+.1f}% (95% CI {eff.low:+.1f} to {eff.high:+.1f}), "
                f"p = {eff.p:.2g}. This is a robustness check and does not change the verdict.", ""]
    return out


def write_report(path, c: dict) -> None:
    feat, args = c["feat"], c["args"]
    kept = len(feat)
    win_num, win_prop, effects = c["win_num"], c["win_prop"], c["effects"]
    base_w, fin_w = win_num.attrs.get("baseline_window"), win_num.attrs.get("final_window")
    L = [
        f"# Pull requests in {c['repo']}: description length, size, speed and labels",
        "",
        f"Window {c['start']} to {c['end']} (UTC). Data fetched {c['fetched_at']:%Y-%m-%d}. prwords {__version__}, "
        f"generated {datetime.now(timezone.utc):%Y-%m-%d}. Method fixed in advance in `docs/ANALYSIS_PLAN.md`.",
        "",
        "## 1. Data",
        "",
        f"- Repository primary language: {c['language'] or 'unknown'}",
        f"- Pull requests opened in the window: {c['n_fetched']:,}",
        f"- Removed as bot accounts: {c['n_bots']:,}" + (f". Removed by weekly author cap: {c['n_capped']:,}" if c["n_capped"] else ""),
        f"- Analysed: {kept:,} PRs from {feat['author'].nunique():,} authors",
        f"- Merged: {int(feat['merged'].sum()):,} ({feat['merged'].mean():.1%}). "
        f"Closed without merging: {int(feat['closed_unmerged'].sum()):,} ({feat['closed_unmerged'].mean():.1%}). "
        f"Still open: {int(feat['is_open'].sum()):,}",
        f"- Follow-up: merge outcomes use a {args.followup_days}-day follow-up. PRs without enough follow-up: "
        f"{int((~feat['followup_ok']).sum()):,}",
        f"- Empty descriptions after cleaning: {(feat['words_prose'] == 0).mean():.1%}",
        "",
        "## 2. Did the PR template change?",
        "",
    ]
    templates = c["templates"]
    changes = templates[templates["change_event"] != ""] if len(templates) else templates
    if len(changes):
        L += ["Lines that appeared or disappeared across the window (full list in `template_audit.csv`):", "",
              _md(changes[["line", "first_month", "last_month", "months", "peak_share", "change_event"]].head(25), 2), ""]
    else:
        L += ["No template line appeared or disappeared with a share of 50% or more. "
              "Template text was detected monthly and removed before counting words.", ""]
    L += [f"Distinct template lines detected: {templates['line'].nunique() if len(templates) else 0}.", "",
          f"## 3. First {args.window_days} days versus last {args.window_days} days", ""]
    if base_w and fin_w:
        L += [f"First window {base_w[0]} to {base_w[1]}. Last window {fin_w[0]} to {fin_w[1]}. "
              "Ratios are last median divided by first median. Bootstrap intervals, 2,000 resamples.", ""]
    L += [_window_numeric_md(win_num), "", _window_prop_md(win_prop), "",
          "## 4. Monthly trends", "", "Theil-Sen slope per month and Kendall tau over full months only.", ""]
    tr = pd.DataFrame([t for t in c["trends"] if "slope_per_month" in t])
    if len(tr):
        L += [_md(tr[["metric", "months", "slope_per_month", "slope_ci_low", "slope_ci_high", "tau", "p"]], 3), ""]
    L += ["![Description length](words_monthly.png)", "", "![Size](size_monthly.png)", "",
          "![Merge rate and time to merge](flow_monthly.png)", "",
          "## 5. Labels", "",
          f"Share of PRs with a kind or type label: {feat['has_kind_label'].mean():.1%} overall. "
          "Label coverage by month is in `monthly_summary.csv` (`share_has_kind_label`).", "",
          _md(c["labels"], 3), "", "![Label categories](labels_monthly.png)", ""]
    sc = c["size_check"]
    if sc is not None and len(sc):
        L += ["Cross-check against the repository's own size labels "
              f"(coverage {sc.attrs['coverage']:.1%}, Spearman rho between size label and lines changed "
              f"{sc.attrs['spearman_rho']:.2f}):", "", _md(sc, 0), ""]
    L += ["## 6. Are PRs with signs of AI involvement smaller or larger?", "",
          "Authorship is not observable. The proxy is `ai_disclosed`, defined in the analysis plan: "
          f"{int(feat['ai_disclosed'].sum()):,} PRs ({feat['ai_disclosed'].mean():.2%}). "
          f"{c['ai_samples_n']} disclosed PRs are listed in `ai_disclosure_samples.csv` for manual audit.", "",
          "![AI signals](ai_signals_monthly.png)", ""]
    verdicts: dict[str, Verdict] = c["verdicts"]
    for exp in verdicts:
        v = verdicts.get(exp)
        L += [f"### {exp}", ""]
        if v:
            L += [f"**Verdict: {v.category}.** {v.explanation}", "", f"Pattern: {v.pattern}.", ""]
            sub = effects[(effects["exposure"] == exp) & effects["permutation_p"].notna() & (effects["outcome"] == "churn")] \
                if "permutation_p" in effects else effects.head(0)
            if len(sub):
                L += [f"Within-author permutation p-value, lines changed: {sub['permutation_p'].iloc[0]:.4f}.", ""]
        L += [_effects_md(effects, exp), ""]
    if (effects["status"] == "ok").any():
        L += ["![Effects](effects.png)", ""]
    L += ["### Robustness by tool (lines changed)", "", _tools_md(c["tools"]), "",
          "### File type check", ""] + _file_md(c["file_res"])
    L += ["## 7. Other checks", "",
          f"- Outside contributors: {feat['is_outside'].mean():.1%} of PRs overall.",
          f"- Top 10 authors opened {feat['author'].value_counts().head(10).sum() / kept:.1%} of PRs.",
          f"- PRs whose description text is repeated elsewhere (10 or more words): {feat['is_duplicate_text'].mean():.1%}.",
          "", "## 8. Limitations", "",
          "- Word count and size describe PRs, not who wrote them. Proxies for AI involvement are noisy and omit undisclosed use.",
          "- Added and deleted lines include generated or vendored files unless the project avoids committing them.",
          "- Disclosure mostly captures tools that add attribution by default, so it is tool-skewed.",
          "- Template removal is heuristic. Check `template_audit.csv`.",
          "- One repository cannot support general claims. See the plan for replication.",
          "- Months at the edges of the window are partial and are excluded from trend tests.", ""]
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


def write_results_json(path, c: dict) -> None:
    def clean(o):
        return None if isinstance(o, float) and np.isnan(o) else o

    effects = c["effects"]
    payload = {
        "repo": c["repo"],
        "language": c["language"],
        "window": [c["start"].isoformat(), c["end"].isoformat()],
        "n_prs": int(len(c["feat"])),
        "verdicts": {k: {"category": v.category, "explanation": v.explanation, "pattern": v.pattern}
                     for k, v in c["verdicts"].items()},
        "window_numeric": json.loads(c["win_num"].to_json(orient="records")),
        "window_proportions": json.loads(c["win_prop"].to_json(orient="records")),
        "trends": [{k: clean(v) for k, v in t.items()} for t in c["trends"]],
        "effects": json.loads(effects.to_json(orient="records")) if len(effects) else [],
        "tools": json.loads(c["tools"].to_json(orient="records")) if len(c["tools"]) else [],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
