"""Draw a reproducible, language-stratified random sample of repositories for the two-window comparison.

Population (the sampling frame): public, non-fork, non-archived repositories created before 2019 with at
least 1,000 stars and a push since 2026-09-01, as returned by GitHub repository search per language and
star band (search returns at most 1,000 per query, so very large bands are truncated).
Eligibility, checked in random order until each stratum is full: 300 to 6,000 PRs opened and at least 150
merged in each window. Repos already analysed are excluded.

Writes batch/repos_sample.txt (one repo per line) and batch/sample_frame.json (frame sizes and every
screened candidate with its counts and the reason it was kept or skipped).
"""
from __future__ import annotations

import json
import os
import random
import time
from pathlib import Path

import requests

SEED = 20261120
PER_STRATUM = 5
STRATA = {
    "Python": ["Python"],
    "JavaScript/TypeScript": ["JavaScript", "TypeScript"],
    "Go": ["Go"],
    "Rust": ["Rust"],
    "Java/Kotlin": ["Java", "Kotlin"],
    "C/C++": ["C", "C++"],
}
STAR_BANDS = ["1000..2999", "3000..9999", ">=10000"]
WINDOWS = {"2023-24": "2023-01-09..2024-08-19", "2025-26": "2025-01-06..2026-08-17"}
MIN_PRS, MAX_PRS, MIN_MERGED = 300, 6000, 150

BATCH = Path(__file__).resolve().parent
session = requests.Session()
session.headers.update({"Authorization": f"bearer {os.environ['GH_TOKEN']}", "Accept": "application/vnd.github+json"})


def search(kind: str, q: str, page: int = 1, per_page: int = 100) -> dict:
    """GitHub search, paced for its 30 requests per minute limit."""
    while True:
        r = session.get(f"https://api.github.com/search/{kind}", params={"q": q, "page": page, "per_page": per_page},
                        timeout=60)
        if r.status_code in (403, 429):
            reset = int(r.headers.get("x-ratelimit-reset", time.time() + 60))
            time.sleep(max(reset - time.time(), 5) + 1)
            continue
        if r.status_code in (502, 503, 504):
            time.sleep(10)
            continue
        r.raise_for_status()
        time.sleep(2.1)
        return r.json()


def frame_for(languages: list[str]) -> list[str]:
    names: set[str] = set()
    for lang in languages:
        for band in STAR_BANDS:
            q = f"language:{lang} stars:{band} created:<2019-01-01 pushed:>=2026-09-01 fork:false archived:false"
            for page in range(1, 11):
                items = search("repositories", q, page)["items"]
                names.update(i["full_name"] for i in items)
                if len(items) < 100:
                    break
    return sorted(names)


def pr_count(repo: str, window: str, merged: bool = False) -> int:
    q = f"repo:{repo} is:pr created:{window}" + (" is:merged" if merged else "")
    return search("issues", q, per_page=1)["total_count"]


def main() -> None:
    exclude = {l.strip().lower() for f in ("repos.txt", "repos_2023.txt")
               for l in (BATCH / f).read_text().splitlines() if l.strip()}
    rng = random.Random(SEED)
    chosen, report = [], {"seed": SEED, "strata": {}}
    for stratum, languages in STRATA.items():
        frame = [r for r in frame_for(languages) if r.lower() not in exclude]
        order = frame[:]
        rng.shuffle(order)
        screened, kept = [], []
        for repo in order:
            if len(kept) == PER_STRATUM:
                break
            counts = {w: pr_count(repo, span) for w, span in WINDOWS.items()}
            ok = all(MIN_PRS <= n <= MAX_PRS for n in counts.values())
            merged = {w: pr_count(repo, span, merged=True) for w, span in WINDOWS.items()} if ok else {}
            ok = ok and all(n >= MIN_MERGED for n in merged.values())
            screened.append({"repo": repo, "prs": counts, "merged": merged, "kept": ok})
            if ok:
                kept.append(repo)
                print(f"{stratum}: {repo} {counts} merged {merged}", flush=True)
        chosen += kept
        report["strata"][stratum] = {"frame_size": len(frame), "screened": screened, "kept": kept}
    (BATCH / "repos_sample.txt").write_text("\n".join(chosen) + "\n")
    (BATCH / "sample_frame.json").write_text(json.dumps(report, indent=1))
    for stratum, r in report["strata"].items():
        print(f"{stratum}: frame {r['frame_size']}, screened {len(r['screened'])}, kept {len(r['kept'])}")


if __name__ == "__main__":
    main()
