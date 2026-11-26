# Analysis plan

Written before any real repository was analysed. Anything not listed here, and anything chosen after
seeing results, is labelled exploratory in the report. Changes are logged under Amendments.

## Why a plan

The study that motivated this work chose two model settings after seeing its result, and its headline
share moved between 36% and 64% depending on the random seed. This plan fixes the question, outcomes,
exposures, tests and the rule for reaching a verdict in advance, so the same criticism cannot be made here.

## The question

Among pull requests opened in the same repository in the same month, are those showing signs of AI
involvement smaller or larger than the others?

The permitted verdicts are **larger**, **smaller**, **no difference detected**, **mixed**, and
**not testable**. "Depends on tool or language" is reported as a finding on top of a verdict, never as a
way to avoid one.

## What the literature says, recorded before data

The published evidence is split, and the split follows study design.

- Larger: a matched same-author comparison of Claude Code PRs found median lines added of 48 against 24,
  with the same number of files. Company-level reports show PR size rising with AI adoption.
- Smaller: two MSR 2026 studies on the AIDev dataset found agent PRs touching fewer files, and one found
  human PRs larger on every size measure. Both compare mostly Codex, Devin and Copilot PRs with a separate
  human sample, without matching on author or repository.

No direction is expected. Neither hypothesis is favoured in the tests.

## Outcomes

**Primary:** size of change, `log(1 + additions + deletions)`, called "lines changed".

**Supporting evidence**, each analysed with the same models:

- `log(1 + files_changed)`
- `log(1 + additions)`
- `log(1 + deletions)`
- `log(1 + hours_to_merge)` (merged PRs only), the timeline measure

Holm adjustment is applied across these five outcomes. Comments, reviews, commits, merge rate and label
mix are described in the monthly tables and are exploratory, not tested against the verdict rule.

## Measuring AI involvement

Authorship cannot be observed. Two proxies are used, and neither is called "AI-written".

| Exposure | Definition | Strength | Weakness |
|---|---|---|---|
| `ai_disclosed` (primary) | The description, or optionally a commit message, names an AI tool in a co-author, assisted-by or "generated with" line | High precision | Low recall. Disclosure habits differ by person, project and tool. Claude Code adds attribution by default and some tools do not |
| `style_flag` (secondary) | The description contains an em dash or one of the study's marker words | Broad coverage | Noisy, mechanically more likely in long text, humans use em dashes |

Every matched `ai_disclosed` snippet is written to `ai_disclosure_samples.csv` so a person can audit
precision. The recommended check is 50 random rows.

## Models

For each exposure and outcome:

- **M1, same month.** Month fixed effects, standard errors clustered by author. In the pooled analysis
  this becomes repository by month fixed effects.
- **M2, plus description length.** Adds `log(1 + words_prose)`. Required for `style_flag`, which depends
  mechanically on length. Interpreted with care for `ai_disclosed`, because AI may change description length.
- **M3, same author.** Author fixed effects, using authors with both exposed and unexposed PRs.
- **Permutation test.** Exposure labels are shuffled among the PRs of the same author 2,000 times and the
  observed within-author difference is compared with that null.

An estimate is reported only when at least 30 exposed PRs exist. Below that, counts are shown and no effect
is claimed.

## Verdict rule

An outcome is **called** in a direction only when the M1 and M3 intervals both exclude zero and agree in
sign. Otherwise it is "no clear difference".

1. Primary called, and none of files, additions or deletions called in the opposite direction:
   **larger** or **smaller**.
2. Primary called, and one of files, additions or deletions called in the opposite direction: **mixed**.
3. Primary not called, M1 excludes zero, M3 does not: **no difference detected**, with the note that the
   same-month gap reflects who discloses AI use, not the PRs themselves.
4. Primary not called otherwise: **no difference detected**, reported with the interval so the size of any
   difference that could still exist is visible.
5. Fewer than 30 exposed PRs, or no author with both exposed and unexposed PRs: **not testable**.

The report also prints one pattern line, for example "lines changed: larger; additions: larger; deletions:
no clear difference; files: no clear difference; time to merge: slower". A result such as more lines added
with the same files is reported as that pattern.

If `ai_disclosed` and `style_flag` give different verdicts, the report says the proxies disagree.

## Language

Language enters in two roles.

- **Confounder:** handled by design. Within a repository, or with repository fixed effects, language is
  constant.
- **Moderator:** does the gap differ by language? Each repository's primary language is read from GitHub
  and estimates are reported per language group. A language with fewer than five repositories carrying an
  estimate is reported as exploratory.

## File type check

Larger could mean lockfiles, generated code or docs. For a sample made of up to 300 exposed PRs and an
equal number of unexposed PRs from the same months, changed files are split into code, tests, docs, config
and generated or lock files. The report gives the line mix for each group and re-estimates the primary
outcome on code and test lines only. This is a robustness check and does not change the verdict.

## Robustness by tool

Where the disclosure text names a tool, the primary outcome is re-estimated per tool with at least 30
exposed PRs. The precedents suggest direction can differ by tool, and a pooled estimate could hide that.
This is a robustness table and does not change the verdict.

## Scaling to many repositories

After the Kubernetes pilot is approved:

- Per-repository estimates where at least 30 exposed PRs exist.
- A pooled random-effects estimate across repositories, with heterogeneity (tau and I squared).
- Language group as a moderator.
- A pattern seen in one repository only is not called a finding.

## What would show the result is right, other than the analyst

- The permutation test, which does not depend on model assumptions.
- Manual audit of `ai_disclosure_samples.csv`.
- Cross-check of computed line counts against the repository's own `size/*` labels, and the file type check.
- Replication of the source study's em dash rate on the same repository.
- A null test on synthetic data, repeated over six seeds, that must call nothing.
- Rerunning on other repositories.

## Known threats

- **Confounding.** Developers who use AI tools may differ in experience, task type and employer.
- **Right censoring.** Recent PRs have not had time to merge. Merge-time results use PRs with at least the
  stated follow-up period, and the report flags any month without it.
- **Generated files.** Added and deleted lines include generated and vendored code unless the project
  avoids committing it. Medians and logs reduce this effect. The `size/*` label and the file type check
  are cross-checks.
- **Disclosure drift.** Disclosure norms and tool defaults change. In October 2026 Linux kernel maintainers
  dropped the requirement to tag AI-assisted patches, so disclosure will undercount over time.
- **Label drift.** Bots add labels on rules that change. Label coverage is reported per month.
- **Template drift.** Addressed by monthly template detection and an audit file.

## Amendments

**Amendment 1.** Made before any real repository was analysed. A synthetic test with no planted effect
produced a false "larger" call. Cause: the few authors who disclose AI use happened to write bigger PRs
anyway. The original rule needed M3 only to agree in sign, and the original permutation test shuffled
labels across authors. The rule now requires both intervals to exclude zero and the permutation shuffles
within author. The synthetic null is tested across six seeds.

**Amendment 2.** Made on 2026-11-17, before any real repository was analysed, after a literature search
showed the evidence is split. Changes:

- Added the five verdict categories and the supporting-outcome rule, including "mixed".
- Recorded the split literature prior.
- Reduced tested outcomes to lines changed, files, additions, deletions and time to merge. Comments and
  reviews became descriptive only.
- Removed the words-per-100-lines question. It does not bear on the size question.
- Added language as moderator, the file type check and robustness by tool.
- Described the pooled multi-repository analysis, to be built after the pilot is approved.

**Amendment 3.** Made on 2026-11-26, after real repositories had been analysed. These changes were
made after seeing results, so everything they touch is exploratory.

- Removed the `style_flag` exposure (em dash or marker word) and the em dash measures. It depends
  mechanically on description length, which is itself an outcome of interest, and it did not bear on
  the questions the study ended up asking. Sections above that mention it are kept as originally written.
- Tool names in the `ai_disclosed` rule now match only as whole words. As a substring, "llm" matched a
  human co-author's name ("Willmer") in python/cpython, found in the disclosure audit.
- Template audit files now mask email addresses, after one repeated line exposed a contributor's email.
- Added the two-window comparison (2023-01-09 to 2024-08-19 against 2025-01-06 to 2026-08-17) across
  45 repositories, including a seeded random sample of 30 (`batch/select_repos.py`). This was not in the
  plan, and no amendment was logged when that work began.
