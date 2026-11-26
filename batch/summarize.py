"""One row per repository from the per-repo results, written to results/_batch/summary.{csv,md}.

Trend columns compare the last three full months with the first three (ratio of their medians, as a
percentage change), marked * when the Theil-Sen slope interval over all full months excludes zero.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from prwords.stats import trend_test  # noqa: E402

TRENDS = {
    "words": "median_words",
    "lines added": "median_additions",
    "lines deleted": "median_deletions",
    "lines changed": "median_churn",
    "files": "median_files_changed",
    "PRs opened": "n_prs",
    "PRs merged": "n_merged",
    "merge rate": "merge_rate",
    "bug share": "share_bug",
}


def trend_cell(monthly: pd.DataFrame, column: str) -> tuple[float | None, bool]:
    t = trend_test(monthly, column)
    if "slope_per_month" not in t:
        return None, False
    full = monthly[~monthly["partial"]].dropna(subset=[column])
    first, last = full[column].head(3).median(), full[column].tail(3).median()
    if not first:
        return None, False
    change = 100 * (last / first - 1)
    return change, t["slope_ci_low"] > 0 or t["slope_ci_high"] < 0


def main() -> None:
    repos = [l.strip() for l in (ROOT / "batch/repos.txt").read_text().splitlines() if l.strip()]
    rows = []
    for repo in repos:
        d = ROOT / "results" / repo.replace("/", "__")
        res = json.loads((d / "results.json").read_text())
        monthly = pd.read_csv(d / "monthly_summary.csv")
        bots = re.search(r"Removed as bot accounts: ([\d,]+)", (d / "report.md").read_text())
        row = {
            "repo": repo,
            "language": res.get("language"),
            "PRs": res["n_prs"],
            "bots removed": int(bots.group(1).replace(",", "")) if bots else None,
        }
        for label, column in TRENDS.items():
            change, sig = trend_cell(monthly, column)
            row[label] = None if change is None else f"{round(change) or 0:+d}%{'*' if sig else ''}"
        eff = pd.DataFrame(res["effects"])
        for exp in ("ai_disclosed",):
            row[f"{exp} n"] = int(eff.loc[eff["exposure"] == exp, "n_exposed"].max())
            row[f"{exp} verdict"] = res["verdicts"][exp]["category"]
        rows.append(row)
    out = pd.DataFrame(rows)
    out.to_csv(ROOT / "results/_batch/summary.csv", index=False)
    (ROOT / "results/_batch/summary.md").write_text(out.to_markdown(index=False) + "\n")
    print(out.to_markdown(index=False))


if __name__ == "__main__":
    main()
