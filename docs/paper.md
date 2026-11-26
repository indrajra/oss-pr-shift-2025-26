# Pull Requests Before and After Agentic Coding Tools: An Observational Look at 45 Open-Source Projects

Nov 25, 2026 · @Rajesh Rathnam

## Abstract

This is an observational study. It describes how pull requests (PRs) changed in open-source projects in 2025–26, compared with the same months of 2023–24. It does not establish that AI caused any of the changes, and it was not designed to.

Description length, lines added and deleted, files changed, PRs opened and the share merged within 30 days were measured for 45 established GitHub projects over two windows of identical length and season: 2023-01-09 to 2024-08-19, and 2025-01-06 to 2026-08-17. ChatGPT and Copilot were already in common use in the first window, so the contrast is between before and after agentic tools. The 45 are 15 hand-picked flagship projects and 30 drawn at random, stratified by language, from active repositories with at least 1,000 stars.

In 2023–24 every measure split roughly evenly between repos trending up and down. In 2025–26 descriptions grew in 40 of 44 repos with data (24 significant, none significantly down). Lines added rose in 35 of 43. PRs opened rose in 35 of 45. The share merged within 30 days fell in 32 of 44 (15 significant, none significantly up). Lines deleted and files changed showed no shift in either window. The effects were strongest in the flagship projects and weaker, though in the same direction, in the random sample.

A proxy for AI involvement (PRs that name an AI tool) was too sparse in most repos to test PR-level differences. The pattern is consistent with, but not evidence of, an AI-driven change in how pull requests are written and merged.

The analysis, the code and this paper were produced with help from Claude Code, an AI coding assistant.

## 1. Introduction

The question is simple: did open-source pull requests change in 2025–26, and did the same projects change the same way before agentic coding tools arrived? Tools that write code and PR text on a developer's behalf (Claude Code, Cursor's agent, Codex, Copilot's agent mode) became widely used during 2025. If they changed how people contribute, some traces should show up in the PR record.

This work was inspired by Louis Abraham's study of pull request vocabulary \[1\], described in \[2\], whose sample window (2025-01-06 to 2026-08-17) is reused here. That study chose model settings after seeing results, and its headline share moved with the random seed. The method, outcomes and verdict rule were fixed in an analysis plan before any real repository was analysed.

The study looks for differences and does not test causes. It reports:

1. Whether description length, PR size, PR volume and merge speed trended in 2025–26.
2. Whether the same projects showed the same trends over the same months of 2023–24.
3. Whether PRs that name an AI tool differ in size from other PRs by the same author in the same month.

The study does not claim that AI tools caused any change, that longer or larger PRs are better or worse, or that the results describe open source as a whole.

## 2. Data and method

Every PR opened in each window was fetched through the GitHub GraphQL API with the `prwords` tool written for this study. Data were fetched on 2026-11-19 and 2026-11-20.

### 2.1 Windows

| Window | Dates (UTC) | Length | Role |
| --- | --- | --- | --- |
| 2023–24 | 2023-01-09 to 2024-08-19 | 588 days | Comparison: after ChatGPT and Copilot, before agentic coding tools |
| 2025–26 | 2025-01-06 to 2026-08-17 | 588 days | Period of interest, matching Abraham's study \[1\] |

Both start on a Monday and cover the same months, so release cycles and holidays line up. Partial months at either end are excluded from trend tests.

### 2.2 Repositories

- **Flagship set (15, hand-picked):** large, long-established projects across Go, Python, JavaScript, Rust, Java, C++ and Ruby, all on GitHub since 2017 or earlier. Five more were analysed for 2025–26 only and are not in the comparison.
- **Random sample (30):** a seeded random draw, 5 per language group (Python, JavaScript/TypeScript, Go, Rust, Java/Kotlin, C/C++). Eligible repos were non-fork, non-archived, created before 2019, with at least 1,000 stars, pushed since 2026-09-01, and with 300 to 6,000 PRs opened and at least 150 merged in each window. About 200 candidates were screened to fill the 30.

**Shared minimum:** all 45 repos were on GitHub before 2019 and have at least 1,000 stars. Only the random 30 were also screened on PR volume (300 to 6,000 opened and at least 150 merged per window). The flagship 15 have not yet been checked against the volume floor.

### 2.3 Measures

- **Description length:** words left after removing HTML comments, code, images, URLs, tags and template lines (lines present in at least 20% of a month's descriptions). Because the rule works month by month, a project that edits its PR template mid-window (Kubernetes did in June 2025) can see word counts shift for that reason alone.
- **Size:** lines added, lines deleted, lines changed (their sum) and files changed. Line counts agreed with Kubernetes's own size labels (Spearman rho 0.95). They include generated and vendored files, which are not filtered out.
- **Flow:** PRs opened per month, PRs merged per month, and the share merged within 30 days of opening. The 30-day share is used instead of the overall merge rate because recent PRs have had less time to be merged.
- **Bots:** accounts typed as bots or named like bots were removed by design. The study observes PRs raised by humans, so PRs opened by agent accounts, such as GitHub's Copilot coding agent, are out of scope.

### 2.4 Trend test

For each repo, window and measure, the monthly median (or share) was taken, then:

- **Direction and size:** median of the last three full months against the median of the first three.
- **Significance:** the Theil-Sen slope across all full months, with its 95% interval. A trend is called significant when the interval excludes zero. Kendall's tau is reported alongside.

The unit of comparison is the count of repos trending up versus down in each window.

### 2.5 AI proxy

- **Disclosed:** the description names an AI tool, as a whole word, in a co-author, assisted-by or "generated with" line. High precision, low recall.
- **Dropped:** an earlier style flag (an em dash or one of six marker words from \[1\]) was removed after results were seen. It rises mechanically with description length, which is itself an outcome here.

For the proxy, PR size was compared within the same month (month fixed effects) and within the same author (author fixed effects, plus a within-author permutation test). A direction was called only when both intervals excluded zero and agreed, and only with at least 30 flagged PRs.

## 3. Results

In 2023–24 the 45 repos split roughly evenly on every measure. In 2025–26 most moved in the same direction: longer descriptions, more lines added, more PRs, and a smaller share merged within 30 days. That last drop could mean slower review, more rejected low-quality PRs, or more drafts and experiments; the data cannot tell these apart.

### 3.1 All 45 repos

How to read each cell: **21 – 19 (6 / 5)** means 21 repos trended up and 19 trended down. Of those, 6 trended up significantly and 5 trended down significantly. The other 29 moved without a significant trend.

| Measure | 2023–24: up – down (sig up / sig down) | 2025–26: up – down (sig up / sig down) |
| --- | --- | --- |
| Description length | 21 – 19 (6 / 5) | **40 – 4 (24 / 0)** |
| Lines added | 20 – 25 (1 / 5) | **35 – 8 (13 / 1)** |
| Lines changed | 21 – 24 (2 / 4) | 31 – 12 (11 / 3) |
| Lines deleted | 22 – 19 (1 / 1) | 20 – 21 (0 / 2) |
| Files changed | 13 – 12 (0 / 0) | 19 – 9 (1 / 0) |
| PRs opened per month | 23 – 22 (8 / 5) | **35 – 10 (15 / 0)** |
| PRs merged per month | 23 – 20 (5 / 6) | 32 – 13 (9 / 1) |
| Share merged within 30 days | 24 – 21 (6 / 4) | **12 – 32 (0 / 15)** |

*Up / down:* the median of a repo's last three full months against its first three (Section 2.4). *Significant:* the Theil-Sen slope's 95% interval excludes zero; significant counts are a subset of the up and down counts. Up plus down can total below 45 where a repo's change was exactly zero or there was too little data to compute it. **Bold** marks the four 2025–26 shifts named in the Abstract.

### 3.2 Flagship versus random sample, 2025–26

The direction is the same in both sets. The flagship projects show it more strongly. Cells read as in Section 3.1.

| Measure | Flagship 15: up – down (sig up / sig down) | Random 30: up – down (sig up / sig down) |
| --- | --- | --- |
| Description length | 15 – 0 (12 / 0) | 25 – 4 (12 / 0) |
| Lines added | 14 – 0 (7 / 0) | 21 – 8 (6 / 1) |
| PRs opened per month | 13 – 2 (9 / 0) | 22 – 8 (6 / 0) |
| Share merged within 30 days | 2 – 13 (0 / 10) | 10 – 19 (0 / 5) |

In 2023–24 the same random 30 split (up – down) 12 – 14 on description length, 13 – 17 on lines added, 15 – 15 on PRs opened and 16 – 14 on the 30-day merge share.

### 3.3 A closer look: Kubernetes

Kubernetes was the pilot. Its 8,615 PRs in 2025–26 show the pattern in detail:

- The monthly median description rose from 31 words (January 2025) to 74 (July 2026), about 2.75 words a month (Kendall tau 0.80).
- It rose within every contributor group: org members 29 to 43 words, contributors 36 to 74, unaffiliated authors 34 to 120.
- The 81 authors active in both early 2025 and mid 2026 wrote descriptions 1.67 times longer, and 63% of them wrote longer ones.
- Median lines added rose from 21 to 70 between the first and last 28 days; deletions and files changed did not move.
- Median time to merge rose sixfold between those 28-day windows, but the monthly trend was flat (p = 0.71). The late window probably fell in a release code freeze.

### 3.4 AI proxy

PR-level tests were mostly underpowered. In the 20 repos analysed for 2025–26 in the first round, named-tool disclosure gave one "larger" verdict (pandas), one "mixed" (cpython), ten "no difference detected" and eight "not testable" (fewer than 30 flagged PRs).

In Kubernetes only 46 PRs (0.5%) named a tool. Compared with the same author's other PRs, tool-naming PRs changed somewhere between 41% fewer and 612% more lines (95% interval). A large effect cannot be ruled out.

Where disclosure was common (pandas, cpython, deno; 500 to 600 PRs each), the matched text was mostly Claude Code's default attribution lines.

## 4. Conclusion

In 45 established open-source projects, PRs in 2025–26 had longer descriptions, added more code and were opened more often. A smaller share were merged within 30 days. Over the same months of 2023–24, the same projects showed no common direction on any of these measures.

The timing matches the spread of agentic AI coding tools, and the descriptive result held in a random sample as well as in flagship projects. A timing match alone does not show that AI caused it. The design has no control group, and the comparison window already had AI assistants. Treat this as an observation that motivates a properly designed study, not as its answer.

## References

1. Louis Abraham. "The load-bearing vocabulary of Claude." [louisabraham.github.io/load-bearing](https://louisabraham.github.io/load-bearing/). Accessed 26 November 2026. The inspiration for this work and the source of its 2025–26 window.
2. Marcus Schuler. "GitHub Pull Request Study Traces AI-Linked Vocabulary From 1% to 45% Since 2025." Implicator.ai, 27 August 2026. [implicator.ai](https://www.implicator.ai/github-pr-ai-linked-vocabulary-1-to-45-percent/). Describes the method of \[1\], including the per-author weekly cap and the variation across model fits.

## Appendix: repositories and reproducibility

### Repositories

| Set | Language group | Repositories |
| --- | --- | --- |
| Flagship | Go | kubernetes/kubernetes, prometheus/prometheus, hashicorp/terraform |
| Flagship | Python | django/django, pandas-dev/pandas, scikit-learn/scikit-learn, python/cpython |
| Flagship | JavaScript | react/react, vercel/next.js, nodejs/node |
| Flagship | Rust, Java, C++, Ruby | tokio-rs/tokio, apache/kafka, keycloak/keycloak, godotengine/godot, rails/rails |
| Random | Python | jupyterhub/jupyterhub, PyPSA/PyPSA, prowler-cloud/prowler, alicevision/Meshroom, Ultimaker/Cura |
| Random | JavaScript/TypeScript | snyk/cli, firebase/firebase-tools, tutao/tutanota, elastic/elasticsearch-js, quiltdata/quilt |
| Random | Go | kubermatic/kubermatic, cortexproject/cortex, flipt-io/flipt, labring/sealos, canonical/lxd |
| Random | Rust | near/nearcore, hermit-os/kernel, rustsec/rustsec, napi-rs/napi-rs, bytecodealliance/wasmtime |
| Random | Java/Kotlin | apache/incubator-seata, OpenFeign/feign, apache/servicecomb-java-chassis, zaproxy/zaproxy, confluentinc/schema-registry |
| Random | C/C++ | NVIDIA/DALI, transmission/transmission, PDAL/PDAL, canonical/multipass, Expensify/Bedrock |

Analysed for 2025–26 only, not in the comparison: microsoft/TypeScript, denoland/deno, duckdb/duckdb, astral-sh/ruff, pola-rs/polars.

### Reproducing the study

- **Tool:** `prwords` 3.0.0 (Python), with 55 offline tests. The method and verdict rule are in `docs/ANALYSIS_PLAN.md`.
- **Sampling:** `batch/select_repos.py`, seed 20261120. Every screened candidate and its PR counts are in `batch/sample_frame.json`.
- **Runs:** `batch/run_pairs.sh` runs both windows per repo; it can be rerun and resumes from cache.
- **Tables:** `batch/compare.py` produced Sections 3.1 and 3.2 (`results_2023/_batch/all45.md`, `sample.md`, `compare.md`).
- **Cost:** GitHub API access is free within rate limits. Fetching about 230,000 PRs took roughly 30 hours of wall-clock time.
