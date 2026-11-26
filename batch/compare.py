"""Compare the 2023-24 window with the 2025-26 window for the repos in one or more lists.

Each cell is "earlier → later": the change from the first three to the last three full months of each
window, marked * when that window's Theil-Sen slope interval excludes zero (see summarize.py).
Written to results_2023/_batch/<name>.{csv,md}, plus a count of repos per direction. Repos without
results for both windows are listed and left out.

    python compare.py                                       # batch/repos_2023.txt -> compare.md
    python compare.py sample repos_sample.txt               # -> sample.md
    python compare.py all45 repos_2023.txt repos_sample.txt
"""
from __future__ import annotations

import sys

import pandas as pd

from summarize import ROOT, TRENDS, trend_cell

WINDOWS = {"2023-24": ROOT / "results_2023", "2025-26": ROOT / "results"}
MEASURES = {k: v for k, v in TRENDS.items() if k != "bug share"}


def cell(change: float | None, sig: bool) -> str:
    return "n/a" if change is None else f"{round(change) or 0:+d}%{'*' if sig else ''}"


def main(name: str = "compare", lists: list[str] | None = None) -> None:
    repos = [l.strip() for f in (lists or ["repos_2023.txt"])
             for l in (ROOT / "batch" / f).read_text().splitlines() if l.strip()]
    missing = [r for r in repos
               if not all((d / r.replace("/", "__") / "monthly_summary.csv").exists() for d in WINDOWS.values())]
    if missing:
        print(f"Left out, not finished in both windows: {', '.join(missing)}\n")
    rows, counts = [], []
    for repo in (r for r in repos if r not in missing):
        monthly = {
            w: pd.read_csv(d / repo.replace("/", "__") / "monthly_summary.csv") for w, d in WINDOWS.items()
        }
        row = {"repo": repo}
        for label, column in MEASURES.items():
            cells = []
            for w, m in monthly.items():
                change, sig = trend_cell(m, column)
                cells.append(cell(change, sig))
                direction = "n/a" if change is None else ("up" if change > 0 else "down" if change < 0 else "flat")
                counts.append({"measure": label, "window": w, "direction": direction, "significant": sig})
            row[label] = " → ".join(cells)
        rows.append(row)

    out = pd.DataFrame(rows)
    c = pd.DataFrame(counts)
    tally = (
        c.assign(sig_up=(c.direction == "up") & c.significant, sig_down=(c.direction == "down") & c.significant)
        .groupby(["measure", "window"], sort=False)
        .agg(up=("direction", lambda s: (s == "up").sum()), down=("direction", lambda s: (s == "down").sum()),
             sig_up=("sig_up", "sum"), sig_down=("sig_down", "sum"))
        .reset_index()
    )
    dest = ROOT / "results_2023/_batch"
    out.to_csv(dest / f"{name}.csv", index=False)
    tally.to_csv(dest / f"{name}_tally.csv", index=False)
    text = f"{len(out)} repos\n\n" + out.to_markdown(index=False) + "\n\n" + tally.to_markdown(index=False) + "\n"
    (dest / f"{name}.md").write_text(text)
    print(text)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:]) if len(sys.argv) > 1 else main()
