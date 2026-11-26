# Pull requests in elastic/elasticsearch-js: description length, size, speed and labels

Window 2023-01-09 to 2024-08-19 (UTC). Data fetched 2026-11-20. prwords 3.0.0, generated 2026-11-26. Method fixed in advance in `docs/ANALYSIS_PLAN.md`.

## 1. Data

- Repository primary language: TypeScript
- Pull requests opened in the window: 459
- Removed as bot accounts: 103
- Analysed: 356 PRs from 31 authors
- Merged: 329 (92.4%). Closed without merging: 27 (7.6%). Still open: 0
- Follow-up: merge outcomes use a 30-day follow-up. PRs without enough follow-up: 0
- Empty descriptions after cleaning: 17.4%

## 2. Did the PR template change?

No template line appeared or disappeared with a share of 50% or more. Template text was detected monthly and removed before counting words.

Distinct template lines detected: 0.

## 3. First 28 days versus last 28 days

First window 2023-01-09 to 2023-02-05. Last window 2024-07-23 to 2024-08-19. Ratios are last median divided by first median. Bootstrap intervals, 2,000 resamples.

| Metric                                |   n first |   n last |   Median first |   Median last |   Ratio |   Ratio low |   Ratio high | p   |   Cliff's delta |
|:--------------------------------------|----------:|---------:|---------------:|--------------:|--------:|------------:|-------------:|:----|----------------:|
| Description words (non-empty)         |         2 |       14 |            nan |           nan |     nan |         nan |          nan | n/a |             nan |
| Files changed                         |         3 |       21 |            nan |           nan |     nan |         nan |          nan | n/a |             nan |
| Lines added                           |         3 |       21 |            nan |           nan |     nan |         nan |          nan | n/a |             nan |
| Lines deleted                         |         3 |       21 |            nan |           nan |     nan |         nan |          nan | n/a |             nan |
| Net lines (added minus deleted)       |         3 |       21 |            nan |           nan |     nan |         nan |          nan | n/a |             nan |
| Lines changed (added plus deleted)    |         3 |       21 |            nan |           nan |     nan |         nan |          nan | n/a |             nan |
| Hours from open to merge (merged PRs) |         3 |       20 |            nan |           nan |     nan |         nan |          nan | n/a |             nan |
| Commits                               |         3 |       21 |            nan |           nan |     nan |         nan |          nan | n/a |             nan |
| Comments                              |         3 |       21 |            nan |           nan |     nan |         nan |          nan | n/a |             nan |
| Reviews                               |         3 |       21 |            nan |           nan |     nan |         nan |          nan | n/a |             nan |

| Measure                             |   n first |   n last | Share first   | Share last   |   Change (points) |     p |
|:------------------------------------|----------:|---------:|:--------------|:-------------|------------------:|------:|
| Merged within follow-up period      |         3 |       21 | 100.0%        | 95.2%        |              -4.8 | 1     |
| Closed without merging              |         3 |       21 | 0.0%          | 4.8%         |               4.8 | 1     |
| Opened as draft                     |         3 |       21 | 0.0%          | 0.0%         |               0   | 1     |
| From outside contributors           |         3 |       21 | 100.0%        | 4.8%         |             -95.2 | 0.002 |
| Has a kind or type label            |         3 |       21 | 0.0%          | 0.0%         |               0   | 1     |
| Description text repeated elsewhere |         3 |       21 | 0.0%          | 0.0%         |               0   | 1     |
| Names an AI tool (disclosure)       |         3 |       21 | 0.0%          | 0.0%         |               0   | 1     |
| Label category: feature             |         3 |       21 | 0.0%          | 0.0%         |               0   | 1     |
| Label category: bug                 |         3 |       21 | 0.0%          | 0.0%         |               0   | 1     |
| Label category: design              |         3 |       21 | 0.0%          | 0.0%         |               0   | 1     |
| Label category: docs                |         3 |       21 | 0.0%          | 0.0%         |               0   | 1     |
| Label category: cleanup             |         3 |       21 | 0.0%          | 0.0%         |               0   | 1     |
| Label category: test                |         3 |       21 | 0.0%          | 0.0%         |               0   | 1     |
| Label category: api_change          |         3 |       21 | 0.0%          | 0.0%         |               0   | 1     |

## 4. Monthly trends

Theil-Sen slope per month and Kendall tau over full months only.

| metric                     |   months |   slope_per_month |   slope_ci_low |   slope_ci_high |     tau |       p |
|:---------------------------|---------:|------------------:|---------------:|----------------:|--------:|--------:|
| median_words               |       18 |            -0.818 |         -1.5   |          -0.3   |  -0.529 |   0.003 |
| median_files_changed       |       18 |             0.125 |         -0     |           0.2   |   0.522 |   0.005 |
| median_additions           |       18 |             0.5   |         -0.25  |           2.385 |   0.304 |   0.081 |
| median_deletions           |       18 |             0.25  |         -0     |           0.714 |   0.361 |   0.04  |
| median_churn               |       18 |             0.6   |         -1.864 |           2.45  |   0.131 |   0.448 |
| median_hours_to_merge      |       18 |            -0.093 |         -1.135 |           0.478 |  -0.072 |   0.709 |
| merge_rate                 |       18 |            -0     |         -0.006 |           0.008 |   0.047 |   0.788 |
| share_outside_contributors |       18 |            -0.011 |         -0.038 |           0.006 |  -0.217 |   0.22  |
| share_ai_disclosed         |       18 |            -0     |         -0     |          -0     | nan     | nan     |
| median_comments            |       18 |            -0     |         -0     |          -0     |  -0.436 |   0.03  |
| median_reviews             |       18 |            -0     |         -0     |           0.056 |   0.116 |   0.556 |
| share_feature              |       18 |            -0     |         -0     |          -0     | nan     | nan     |
| share_bug                  |       18 |            -0     |         -0     |          -0     | nan     | nan     |
| share_design               |       18 |            -0     |         -0     |          -0     | nan     | nan     |
| share_docs                 |       18 |            -0     |         -0     |          -0     |   0.464 |   0.021 |
| share_cleanup              |       18 |            -0     |         -0     |          -0     | nan     | nan     |
| share_test                 |       18 |            -0     |         -0     |          -0     | nan     | nan     |
| share_api_change           |       18 |            -0     |         -0     |          -0     | nan     | nan     |

![Description length](words_monthly.png)

![Size](size_monthly.png)

![Merge rate and time to merge](flow_monthly.png)

## 5. Labels

Share of PRs with a kind or type label: 0.0% overall. Label coverage by month is in `monthly_summary.csv` (`share_has_kind_label`).

| category            |   n_prs |   share |   median_words |   median_files |   median_churn |   merge_rate |   median_hours_to_merge |   share_ai_disclosed |
|:--------------------|--------:|--------:|---------------:|---------------:|---------------:|-------------:|------------------------:|---------------------:|
| feature             |       0 |   0     |          nan   |          nan   |          nan   |      nan     |                 nan     |                  nan |
| bug                 |       0 |   0     |          nan   |          nan   |          nan   |      nan     |                 nan     |                  nan |
| design              |       0 |   0     |          nan   |          nan   |          nan   |      nan     |                 nan     |                  nan |
| docs                |       2 |   0.006 |           77   |            2.5 |           19.5 |        0.5   |                   6.46  |                    0 |
| cleanup             |       0 |   0     |          nan   |          nan   |          nan   |      nan     |                 nan     |                  nan |
| test                |       0 |   0     |          nan   |          nan   |          nan   |      nan     |                 nan     |                  nan |
| api_change          |       0 |   0     |          nan   |          nan   |          nan   |      nan     |                 nan     |                  nan |
| (no category label) |     354 |   0.994 |            6.5 |            2   |           14.5 |        0.927 |                   4.594 |                    0 |

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

- Outside contributors: 14.3% of PRs overall.
- Top 10 authors opened 93.8% of PRs.
- PRs whose description text is repeated elsewhere (10 or more words): 2.8%.

## 8. Limitations

- Word count and size describe PRs, not who wrote them. Proxies for AI involvement are noisy and omit undisclosed use.
- Added and deleted lines include generated or vendored files unless the project avoids committing them.
- Disclosure mostly captures tools that add attribution by default, so it is tool-skewed.
- Template removal is heuristic. Check `template_audit.csv`.
- One repository cannot support general claims. See the plan for replication.
- Months at the edges of the window are partial and are excluded from trend tests.

