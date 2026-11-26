# Pull requests in apache/servicecomb-java-chassis: description length, size, speed and labels

Window 2025-01-06 to 2026-08-17 (UTC). Data fetched 2026-11-20. prwords 3.0.0, generated 2026-11-26. Method fixed in advance in `docs/ANALYSIS_PLAN.md`.

## 1. Data

- Repository primary language: Java
- Pull requests opened in the window: 374
- Removed as bot accounts: 235
- Analysed: 139 PRs from 19 authors
- Merged: 124 (89.2%). Closed without merging: 12 (8.6%). Still open: 3
- Follow-up: merge outcomes use a 30-day follow-up. PRs without enough follow-up: 0
- Empty descriptions after cleaning: 30.9%

## 2. Did the PR template change?

No template line appeared or disappeared with a share of 50% or more. Template text was detected monthly and removed before counting words.

Distinct template lines detected: 0.

## 3. First 28 days versus last 28 days

First window 2025-01-06 to 2025-02-02. Last window 2026-07-21 to 2026-08-17. Ratios are last median divided by first median. Bootstrap intervals, 2,000 resamples.

| Metric                                |   n first |   n last |   Median first |   Median last |   Ratio |   Ratio low |   Ratio high | p   |   Cliff's delta |
|:--------------------------------------|----------:|---------:|---------------:|--------------:|--------:|------------:|-------------:|:----|----------------:|
| Description words (non-empty)         |         3 |        0 |            nan |           nan |     nan |         nan |          nan | n/a |             nan |
| Files changed                         |        13 |        0 |            nan |           nan |     nan |         nan |          nan | n/a |             nan |
| Lines added                           |        13 |        0 |            nan |           nan |     nan |         nan |          nan | n/a |             nan |
| Lines deleted                         |        13 |        0 |            nan |           nan |     nan |         nan |          nan | n/a |             nan |
| Net lines (added minus deleted)       |        13 |        0 |            nan |           nan |     nan |         nan |          nan | n/a |             nan |
| Lines changed (added plus deleted)    |        13 |        0 |            nan |           nan |     nan |         nan |          nan | n/a |             nan |
| Hours from open to merge (merged PRs) |        13 |        0 |            nan |           nan |     nan |         nan |          nan | n/a |             nan |
| Commits                               |        13 |        0 |            nan |           nan |     nan |         nan |          nan | n/a |             nan |
| Comments                              |        13 |        0 |            nan |           nan |     nan |         nan |          nan | n/a |             nan |
| Reviews                               |        13 |        0 |            nan |           nan |     nan |         nan |          nan | n/a |             nan |

| Measure                             |   n first |   n last | Share first   | Share last   |   Change (points) | p   |
|:------------------------------------|----------:|---------:|:--------------|:-------------|------------------:|:----|
| Merged within follow-up period      |        13 |        0 | n/a           | n/a          |               nan | n/a |
| Closed without merging              |        13 |        0 | n/a           | n/a          |               nan | n/a |
| Opened as draft                     |        13 |        0 | n/a           | n/a          |               nan | n/a |
| From outside contributors           |        13 |        0 | n/a           | n/a          |               nan | n/a |
| Has a kind or type label            |        13 |        0 | n/a           | n/a          |               nan | n/a |
| Description text repeated elsewhere |        13 |        0 | n/a           | n/a          |               nan | n/a |
| Names an AI tool (disclosure)       |        13 |        0 | n/a           | n/a          |               nan | n/a |
| Label category: feature             |        13 |        0 | n/a           | n/a          |               nan | n/a |
| Label category: bug                 |        13 |        0 | n/a           | n/a          |               nan | n/a |
| Label category: design              |        13 |        0 | n/a           | n/a          |               nan | n/a |
| Label category: docs                |        13 |        0 | n/a           | n/a          |               nan | n/a |
| Label category: cleanup             |        13 |        0 | n/a           | n/a          |               nan | n/a |
| Label category: test                |        13 |        0 | n/a           | n/a          |               nan | n/a |
| Label category: api_change          |        13 |        0 | n/a           | n/a          |               nan | n/a |

## 4. Monthly trends

Theil-Sen slope per month and Kendall tau over full months only.

| metric                     |   months |   slope_per_month |   slope_ci_low |   slope_ci_high |     tau |       p |
|:---------------------------|---------:|------------------:|---------------:|----------------:|--------:|--------:|
| median_words               |       17 |            -0     |         -1.417 |          -0     |  -0.086 |   0.654 |
| median_files_changed       |       17 |            -0     |         -0.308 |           0.188 |  -0.112 |   0.548 |
| median_additions           |       17 |            -0.299 |         -3     |           1.833 |  -0.104 |   0.563 |
| median_deletions           |       17 |            -0.354 |         -1     |           0.182 |  -0.232 |   0.199 |
| median_churn               |       17 |            -2.422 |         -7     |           1.667 |  -0.258 |   0.149 |
| median_hours_to_merge      |       15 |             1.551 |        -18.876 |          21.903 |   0.048 |   0.846 |
| merge_rate                 |       17 |            -0.021 |         -0.033 |          -0     |  -0.4   |   0.036 |
| share_outside_contributors |       17 |            -0     |         -0     |          -0     |   0.55  |   0.007 |
| share_ai_disclosed         |       17 |            -0     |         -0     |          -0     | nan     | nan     |
| median_comments            |       17 |            -0     |         -0     |          -0     |  -0.3   |   0.153 |
| median_reviews             |       17 |            -0     |         -0     |          -0     |  -0.058 |   0.77  |
| share_feature              |       17 |            -0     |         -0     |          -0     | nan     | nan     |
| share_bug                  |       17 |            -0     |         -0     |          -0     | nan     | nan     |
| share_design               |       17 |            -0     |         -0     |          -0     | nan     | nan     |
| share_docs                 |       17 |            -0     |         -0     |          -0     | nan     | nan     |
| share_cleanup              |       17 |            -0     |         -0     |          -0     | nan     | nan     |
| share_test                 |       17 |            -0     |         -0     |          -0     | nan     | nan     |
| share_api_change           |       17 |            -0     |         -0     |          -0     | nan     | nan     |

![Description length](words_monthly.png)

![Size](size_monthly.png)

![Merge rate and time to merge](flow_monthly.png)

## 5. Labels

Share of PRs with a kind or type label: 0.0% overall. Label coverage by month is in `monthly_summary.csv` (`share_has_kind_label`).

| category            |   n_prs |   share |   median_words |   median_files |   median_churn |   merge_rate |   median_hours_to_merge |   share_ai_disclosed |
|:--------------------|--------:|--------:|---------------:|---------------:|---------------:|-------------:|------------------------:|---------------------:|
| feature             |       0 |       0 |            nan |            nan |            nan |      nan     |                 nan     |                  nan |
| bug                 |       0 |       0 |            nan |            nan |            nan |      nan     |                 nan     |                  nan |
| design              |       0 |       0 |            nan |            nan |            nan |      nan     |                 nan     |                  nan |
| docs                |       0 |       0 |            nan |            nan |            nan |      nan     |                 nan     |                  nan |
| cleanup             |       0 |       0 |            nan |            nan |            nan |      nan     |                 nan     |                  nan |
| test                |       0 |       0 |            nan |            nan |            nan |      nan     |                 nan     |                  nan |
| api_change          |       0 |       0 |            nan |            nan |            nan |      nan     |                 nan     |                  nan |
| (no category label) |     139 |       1 |            142 |              2 |             19 |        0.892 |                  26.509 |                    0 |

![Label categories](labels_monthly.png)

## 6. Are PRs with signs of AI involvement smaller or larger?

Authorship is not observable. The proxy is `ai_disclosed`, defined in the analysis plan: 0 PRs (0.00%). 0 disclosed PRs are listed in `ai_disclosure_samples.csv` for manual audit.

![AI signals](ai_signals_monthly.png)

### ai_disclosed

**Verdict: not testable.** Too few exposed PRs.

Pattern: lines changed: not estimated; files changed: not estimated; lines added: not estimated; lines deleted: not estimated; hours to merge: not estimated.

Not estimated: fewer than 30 exposed PRs (exposed PRs: 0).

### Robustness by tool (lines changed)

No tool named in any disclosure.

### File type check

Not run. Use `--file-check N` to sample N exposed PRs and matching unexposed PRs.

## 7. Other checks

- Outside contributors: 94.2% of PRs overall.
- Top 10 authors opened 92.8% of PRs.
- PRs whose description text is repeated elsewhere (10 or more words): 41.7%.

## 8. Limitations

- Word count and size describe PRs, not who wrote them. Proxies for AI involvement are noisy and omit undisclosed use.
- Added and deleted lines include generated or vendored files unless the project avoids committing them.
- Disclosure mostly captures tools that add attribution by default, so it is tool-skewed.
- Template removal is heuristic. Check `template_audit.csv`.
- One repository cannot support general claims. See the plan for replication.
- Months at the edges of the window are partial and are excluded from trend tests.

