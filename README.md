# oss-pr-shift-2025-26

An observational look at how pull requests changed in 45 open-source projects in 2025–26, compared
with the same months of 2023–24. It describes differences; it does not show that AI tools caused them.

- **Paper:** [`docs/paper.md`](docs/paper.md)
- **Headline tables:** [`results_2023/_batch/all45.md`](results_2023/_batch/all45.md) (all 45 repos),
  [`sample.md`](results_2023/_batch/sample.md) (random 30), [`compare.md`](results_2023/_batch/compare.md) (flagship 15)
- **Per-repo results:** `results/<owner>__<name>/` (2025–26) and `results_2023/<owner>__<name>/` (2023–24)
- **Repo sample:** [`batch/select_repos.py`](batch/select_repos.py), seed 20261120; every screened candidate in
  [`batch/sample_frame.json`](batch/sample_frame.json)

Per-PR files (which name each PR's author) and the raw API caches are not published. Rerun the tool to
regenerate them: `batch/run_pairs.sh batch/repos_sample.txt`.

The analysis, the code and the paper were produced with help from Claude Code.

## prwords

Measures pull request descriptions, size, speed and labels for a GitHub repository, and tests whether
PRs that name an AI tool are smaller or larger than others. Inspired by Louis Abraham's study of PR
description vocabulary, ["The load-bearing vocabulary of Claude"](https://louisabraham.github.io/load-bearing/),
whose sample window (2025-01-06 to 2026-08-17) this work reuses; its method is described in an
[Implicator.ai write-up](https://www.implicator.ai/github-pr-ai-linked-vocabulary-1-to-45-percent/).

The method, outcomes and the rule for reaching a verdict are fixed in advance in
[`docs/ANALYSIS_PLAN.md`](docs/ANALYSIS_PLAN.md). Read it first. Changes are logged there as amendments.

## Quick start

```bash
pip install -r requirements.txt
export GH_TOKEN=<token with public repo read access>
python -m prwords kubernetes/kubernetes
```

Large repositories need several hundred API requests. The run is cached and resumable, honours the rate
limit, and halves its page size automatically if GitHub times out. The file type check adds up to about
600 small requests. Use `--file-check 0` to skip it.

| Option | Purpose |
|---|---|
| `--with-commit-messages` | Also scan commit messages for AI co-author lines. Slower, heavier API use |
| `--file-check 300` | Sample N exposed PRs (plus matching others) for the file type check. 0 skips it |
| `--author-weekly-cap 3` | At most 3 PRs per author per week, as in Abraham's study |
| `--label-map labels.json` | Your own `{"category": ["regex", ...]}` mapping for a repository's labels |
| `--followup-days 30` | Follow-up period for merge outcomes |
| `--n-perm 2000`, `--n-boot 1000` | Permutation and bootstrap sizes |

## The question and the verdict

Among PRs opened in the same repository in the same month, are those showing signs of AI involvement
smaller or larger? The primary outcome is lines changed. Files, additions, deletions and time to merge
are supporting evidence.

An outcome is called only when the same-month and same-author intervals both exclude zero and agree.
The verdict is one of **larger**, **smaller**, **no difference detected**, **mixed** or **not testable**,
printed with a pattern line such as "lines changed: larger; files changed: no clear difference".
The rule is deliberately conservative. With few disclosing authors the same-month check is noisy, so a
real effect can go uncalled. The report shows the intervals so that case is visible.

## Outputs

Written to `results/<owner>__<name>/`:

| File | Content |
|---|---|
| `report.md` | Everything below in one readable report, including the verdicts |
| `results.json` | The same numbers, machine readable |
| `pr_features.csv` | One row per PR with every derived field, including repository language |
| `monthly_summary.csv` | About 60 metrics per month |
| `window_numeric.csv`, `window_proportions.csv` | First 28 days versus last 28 days |
| `label_summary.csv` | Volume, size, speed and description length per label category |
| `template_audit.csv`, `template_lines_summary.csv` | Which lines were treated as template, and when they appeared or vanished |
| `exposure_effects.csv` | Exposed versus other PRs, three models, permutation p, Holm adjusted p |
| `tool_robustness.csv` | Lines changed effect per named tool |
| `file_type_sample.csv`, `file_type_mix.csv` | Line mix by file type for the sampled PRs |
| `ai_disclosure_samples.csv` | 50 random disclosed PRs with the matched text and tool, for manual audit |
| `*_monthly.png`, `effects.png` | Six charts |

## Method in brief

1. **Fetch** every PR created in the window through the GraphQL API, with state, merge time, files,
   additions, deletions, labels, comments, reviews, commit count and the repository's primary language.
2. **Filter** bot accounts. Optionally cap PRs per author per week.
3. **Clean** descriptions. Remove HTML comments, code, images, URLs and tags. Detect template lines per
   calendar month and remove them. Every template line is logged with its first and last month.
4. **Measure** words, size, flow and label categories (feature, bug, design, docs, cleanup, test, API change).
5. **Compare** first and last 28 days with bootstrap intervals, plus monthly Theil-Sen and Kendall trends.
6. **Test the AI question** with one proxy, never called "AI-written": `ai_disclosed` (a line names an AI
   tool). Models: M1 same month, M2 plus description length, M3 same author, plus a within-author
   permutation test. An earlier em dash and marker word proxy was removed (Amendment 3 in the plan).
7. **Check robustness** by tool and by file type (code and tests versus docs, config and generated files).

Language is handled by design inside one repository. Across repositories it becomes a moderator, reported
per language group (see the plan). The pooled multi-repository analysis is not built yet. It follows once
the pilot is approved.

## Tests

```bash
python -m pytest -q
```

Fifty-five offline tests cover counting, cleaning, mid-quarter template changes, AI disclosure patterns,
tool extraction, label rules, file type rules, bot filtering, API paging, cache resume, page size halving,
the verdict rule (larger, smaller, mixed, no difference, not testable) and end-to-end runs on synthetic
data. The synthetic data plants a smaller effect, a larger effect and no effect. The pipeline must recover
the first two and, across six seeds, call nothing in the third.

## Limitations

- Authorship is not observable. Proxies are noisy, and undisclosed use is invisible. Disclosure mostly
  captures tools that add attribution by default.
- Added and deleted lines include generated or vendored files unless the project avoids committing them.
  The `size/*` labels and the file type check are cross-checks.
- Label rules differ by repository. Check `label_summary.csv` and supply `--label-map` if needed.
- Repositories that auto-close PRs (such as the Linux kernel mirror) measure bot text. Mailing list
  projects need a different source.
- One repository cannot support general claims. Replicate before concluding.
