"""Statistics: monthly tables, window comparisons, trends, label patterns and exposure effects."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

from .labels import SIZE_ORDER

SEED = 42

# (column, label, restrict_to) used for numeric window comparisons and monthly medians.
NUMERIC_METRICS = [
    ("words_prose", "Description words (non-empty)", "nonempty"),
    ("files_changed", "Files changed", None),
    ("additions", "Lines added", None),
    ("deletions", "Lines deleted", None),
    ("net_lines", "Net lines (added minus deleted)", None),
    ("churn", "Lines changed (added plus deleted)", None),
    ("hours_to_merge", "Hours from open to merge (merged PRs)", "merged"),
    ("commits", "Commits", None),
    ("comments", "Comments", None),
    ("reviews", "Reviews", None),
]

OUTCOMES = {
    "churn": "Lines changed",
    "files_changed": "Files changed",
    "additions": "Lines added",
    "deletions": "Lines deleted",
    "hours_to_merge": "Hours to merge",
}
PRIMARY = "churn"
SIZE_SUPPORT = ("files_changed", "additions", "deletions")


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def bootstrap_median_ci(values: np.ndarray, rng: np.random.Generator, n_boot: int = 1000):
    values = values[~np.isnan(values)]
    if len(values) < 5:
        return np.nan, np.nan
    draws = rng.choice(values, size=(n_boot, len(values)), replace=True)
    lo, hi = np.percentile(np.median(draws, axis=1), [2.5, 97.5])
    return float(lo), float(hi)


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return np.nan, np.nan
    p = k / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    half = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return float(centre - half), float(centre + half)


def _subset(df: pd.DataFrame, col: str, restrict: str | None) -> np.ndarray:
    vals = df[col]
    if restrict == "nonempty":
        vals = vals[df["words_prose"] > 0]
    elif restrict == "merged":
        vals = vals[df["merged"]]
    return vals.dropna().to_numpy(dtype=float)


def _is_partial(month: str, start: date, end: date) -> bool:
    p = pd.Period(month, "M")
    return p.start_time.date() < start or p.end_time.date() > end


def holm(pvalues: list[float]) -> list[float]:
    """Holm step-down adjustment."""
    p = np.asarray(pvalues, dtype=float)
    order = np.argsort(p)
    m = len(p)
    adj = np.empty(m)
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, (m - rank) * p[idx])
        adj[idx] = min(1.0, running)
    return adj.tolist()


# --------------------------------------------------------------------------- #
# Monthly table
# --------------------------------------------------------------------------- #
def monthly_table(
    df: pd.DataFrame, start: date, end: date, cat_cols: list[str], n_boot: int = 1000, seed: int = SEED
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for month, g in df.groupby("month"):
        n = len(g)
        row: dict = {
            "month": month,
            "partial": _is_partial(month, start, end),
            "n_prs": n,
            "n_authors": g["author"].nunique(),
            "n_merged": int(g["merged"].sum()),
            "merge_rate": float(g["merged"].mean()),
            "share_closed_unmerged": float(g["closed_unmerged"].mean()),
            "share_open": float(g["is_open"].mean()),
            "merged_in_followup": float(g["merged_in_followup"].dropna().mean())
            if g["merged_in_followup"].notna().any()
            else np.nan,
        }
        for col, _, restrict in NUMERIC_METRICS:
            vals = _subset(g, col, restrict)
            short = {"words_prose": "words", "hours_to_merge": "hours_to_merge"}.get(col, col)
            row[f"median_{short}"] = float(np.median(vals)) if len(vals) else np.nan
            if col in ("words_prose", "files_changed", "churn", "hours_to_merge"):
                lo, hi = bootstrap_median_ci(vals, rng, n_boot)
                row[f"median_{short}_ci_low"], row[f"median_{short}_ci_high"] = lo, hi
            if col in ("words_prose", "churn", "hours_to_merge"):
                row[f"p25_{short}"], row[f"p75_{short}"], row[f"p90_{short}"] = (
                    (np.percentile(vals, [25, 75, 90]) if len(vals) else [np.nan] * 3)
                )
        row["mean_words"] = float(_subset(g, "words_prose", "nonempty").mean()) if (g["words_prose"] > 0).any() else np.nan
        row["share_empty_description"] = float((g["words_prose"] == 0).mean())
        row["share_draft"] = float(g["is_draft"].mean())
        row["share_outside_contributors"] = float(g["is_outside"].mean())
        row["share_has_kind_label"] = float(g["has_kind_label"].mean())
        row["share_duplicate_text"] = float(g["is_duplicate_text"].mean())
        row["share_ai_disclosed"] = float(g["ai_disclosed"].mean())
        row["top10_author_share"] = float(g["author"].value_counts().head(10).sum() / n)
        for c in cat_cols:
            row[f"share_{c.removeprefix('cat_')}"] = float(g[c].mean())
        rows.append(row)
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# First window versus last window
# --------------------------------------------------------------------------- #
def _window_slices(df: pd.DataFrame, start: date, end: date, days: int):
    ts = df["created_at"].dt.tz_convert(None).dt.date
    b_end = start + timedelta(days=days - 1)
    f_start = end - timedelta(days=days - 1)
    base = df[(ts >= start) & (ts <= b_end)]
    fin = df[(ts >= f_start) & (ts <= end)]
    return base, fin, (start, b_end), (f_start, end)


def window_numeric_table(
    df: pd.DataFrame, start: date, end: date, days: int = 28, n_boot: int = 2000, seed: int = SEED
) -> pd.DataFrame:
    """First ``days`` versus last ``days``: medians, ratio with bootstrap interval, Mann-Whitney, Cliff's delta."""
    rng = np.random.default_rng(seed)
    base_df, fin_df, bw, fw = _window_slices(df, start, end, days)
    rows = []
    for col, label, restrict in NUMERIC_METRICS:
        b, f = _subset(base_df, col, restrict), _subset(fin_df, col, restrict)
        row = {"metric": col, "label": label, "n_baseline": len(b), "n_final": len(f)}
        if len(b) < 5 or len(f) < 5:
            rows.append(row)
            continue
        mb, mf = float(np.median(b)), float(np.median(f))
        boot_b = np.median(rng.choice(b, (n_boot, len(b))), axis=1)
        boot_f = np.median(rng.choice(f, (n_boot, len(f))), axis=1)
        diff_lo, diff_hi = np.percentile(boot_f - boot_b, [2.5, 97.5])
        with np.errstate(divide="ignore", invalid="ignore"):
            ratio_draws = np.where(boot_b > 0, boot_f / boot_b, np.nan)
        ratio_ci = np.nanpercentile(ratio_draws, [2.5, 97.5]) if np.isfinite(ratio_draws).sum() > 100 else (np.nan, np.nan)
        u = stats.mannwhitneyu(f, b, alternative="two-sided")
        row.update(
            median_baseline=mb,
            median_final=mf,
            difference=mf - mb,
            difference_ci_low=float(diff_lo),
            difference_ci_high=float(diff_hi),
            ratio=mf / mb if mb > 0 else np.nan,
            ratio_ci_low=float(ratio_ci[0]),
            ratio_ci_high=float(ratio_ci[1]),
            mannwhitney_p=float(u.pvalue),
            cliffs_delta=float(2 * u.statistic / (len(f) * len(b)) - 1),
        )
        rows.append(row)
    out = pd.DataFrame(rows)
    out.attrs["baseline_window"] = bw
    out.attrs["final_window"] = fw
    return out


PROPORTION_METRICS = [
    ("merged_in_followup", "Merged within follow-up period"),
    ("closed_unmerged", "Closed without merging"),
    ("is_draft", "Opened as draft"),
    ("is_outside", "From outside contributors"),
    ("has_kind_label", "Has a kind or type label"),
    ("is_duplicate_text", "Description text repeated elsewhere"),
    ("ai_disclosed", "Names an AI tool (disclosure)"),
]


def window_proportion_table(
    df: pd.DataFrame, start: date, end: date, cat_cols: list[str], days: int = 28
) -> pd.DataFrame:
    base_df, fin_df, _, _ = _window_slices(df, start, end, days)
    metrics = PROPORTION_METRICS + [(c, f"Label category: {c.removeprefix('cat_')}") for c in cat_cols]
    rows = []
    for col, label in metrics:
        b, f = base_df[col].dropna().astype(float), fin_df[col].dropna().astype(float)
        row = {"metric": col, "label": label, "n_baseline": len(b), "n_final": len(f)}
        if len(b) and len(f):
            kb, kf = int(b.sum()), int(f.sum())
            blo, bhi = wilson_ci(kb, len(b))
            flo, fhi = wilson_ci(kf, len(f))
            _, p = stats.fisher_exact([[kf, len(f) - kf], [kb, len(b) - kb]])
            row.update(
                share_baseline=kb / len(b), baseline_ci_low=blo, baseline_ci_high=bhi,
                share_final=kf / len(f), final_ci_low=flo, final_ci_high=fhi,
                change_points=100 * (kf / len(f) - kb / len(b)), fisher_p=float(p),
            )
        rows.append(row)
    # Fixed columns, so a window with no PRs gives empty cells rather than missing columns.
    return pd.DataFrame(rows, columns=[
        "metric", "label", "n_baseline", "n_final", "share_baseline", "baseline_ci_low", "baseline_ci_high",
        "share_final", "final_ci_low", "final_ci_high", "change_points", "fisher_p",
    ])


# --------------------------------------------------------------------------- #
# Trends
# --------------------------------------------------------------------------- #
def trend_test(monthly: pd.DataFrame, column: str, exclude_partial: bool = True) -> dict:
    m = monthly[~monthly["partial"]] if exclude_partial else monthly
    m = m.dropna(subset=[column])
    if len(m) < 6:
        return {"metric": column, "months": len(m)}
    x = np.arange(len(m))
    slope, _, lo, hi = stats.theilslopes(m[column].to_numpy(), x)
    tau, p = stats.kendalltau(x, m[column].to_numpy())
    return {
        "metric": column,
        "months": len(m),
        "slope_per_month": float(slope),
        "slope_ci_low": float(lo),
        "slope_ci_high": float(hi),
        "tau": float(tau),
        "p": float(p),
    }


# --------------------------------------------------------------------------- #
# Labels
# --------------------------------------------------------------------------- #
def label_table(df: pd.DataFrame, cat_cols: list[str]) -> pd.DataFrame:
    """Per label category: volume and how those PRs differ in description length, size and flow."""
    groups = {c.removeprefix("cat_"): df[df[c]] for c in cat_cols}
    groups["(no category label)"] = df[~df[cat_cols].any(axis=1)]
    rows = []
    for name, g in groups.items():
        ne = g[g["words_prose"] > 0]
        rows.append(
            {
                "category": name,
                "n_prs": len(g),
                "share": len(g) / len(df),
                "median_words": float(ne["words_prose"].median()) if len(ne) else np.nan,
                "median_files": float(g["files_changed"].median()) if len(g) else np.nan,
                "median_churn": float(g["churn"].median()) if len(g) else np.nan,
                "merge_rate": float(g["merged"].mean()) if len(g) else np.nan,
                "median_hours_to_merge": float(g["hours_to_merge"].median()) if len(g) else np.nan,
                "share_ai_disclosed": float(g["ai_disclosed"].mean()) if len(g) else np.nan,
            }
        )
    return pd.DataFrame(rows)


def size_label_check(df: pd.DataFrame) -> pd.DataFrame:
    """Compare computed lines changed with the repository's own size labels."""
    g = df.dropna(subset=["size_label"])
    if g.empty:
        return pd.DataFrame()
    out = (
        g.groupby("size_label")
        .agg(n_prs=("number", "size"), median_churn=("churn", "median"),
             p10_churn=("churn", lambda s: s.quantile(0.1)), p90_churn=("churn", lambda s: s.quantile(0.9)))
        .reindex([s for s in SIZE_ORDER if s in set(g["size_label"])])
        .reset_index()
    )
    rho, _ = stats.spearmanr(g["size_label"].map({s: i for i, s in enumerate(SIZE_ORDER)}), g["churn"])
    out.attrs["spearman_rho"] = float(rho)
    out.attrs["coverage"] = float(df["size_label"].notna().mean())
    return out


# --------------------------------------------------------------------------- #
# Exposure effects
# --------------------------------------------------------------------------- #
@dataclass
class Effect:
    pct: float
    low: float
    high: float
    p: float


def _pct(coef: float, lo: float, hi: float, p: float) -> Effect:
    return Effect((np.exp(coef) - 1) * 100, (np.exp(lo) - 1) * 100, (np.exp(hi) - 1) * 100, float(p))


def _fit_month_fe(d: pd.DataFrame, with_length: bool) -> Effect:
    X = pd.get_dummies(d["month"], drop_first=True, dtype=float)
    X.insert(0, "x", d["x"].astype(float))
    if with_length:
        X["log_words"] = np.log1p(d["words_prose"])
    X = sm.add_constant(X)
    res = sm.OLS(d["y"].to_numpy(), X).fit(cov_type="cluster", cov_kwds={"groups": d["author_code"].to_numpy()})
    lo, hi = res.conf_int().loc["x"]
    return _pct(res.params["x"], lo, hi, res.pvalues["x"])


def _fit_author_fe(d: pd.DataFrame) -> Effect | None:
    """Within-author estimate using authors who have both exposed and unexposed PRs."""
    both = d.groupby("author_code")["x"].agg(["min", "max"])
    keep = both.index[(both["min"] == 0) & (both["max"] == 1)]
    d = d[d["author_code"].isin(keep)]
    if d["x"].sum() < 10 or (1 - d["x"]).sum() < 10 or len(keep) < 5:
        return None
    months = pd.get_dummies(d["month"], drop_first=True, dtype=float)
    X = months.copy()
    X.insert(0, "x", d["x"].astype(float))
    Xd = X - X.groupby(d["author_code"].to_numpy()).transform("mean")
    yd = d["y"] - d.groupby("author_code")["y"].transform("mean")
    res = sm.OLS(yd.to_numpy(), Xd).fit(cov_type="cluster", cov_kwds={"groups": d["author_code"].to_numpy()})
    lo, hi = res.conf_int().loc["x"]
    return _pct(res.params["x"], lo, hi, res.pvalues["x"])


def _permutation_p(
    y: np.ndarray, x: np.ndarray, strata: np.ndarray, n_perm: int, rng: np.random.Generator
) -> tuple[float, float]:
    """Stratified difference in means and its permutation p-value (labels shuffled within strata).

    Strata with no exposed or no unexposed PRs carry zero weight, so with author strata this is a
    within-author comparison."""
    order = np.argsort(strata, kind="stable")
    y, x, strata = y[order], x[order].astype(float), strata[order]
    _, codes = np.unique(strata, return_inverse=True)
    k = codes.max() + 1
    size = np.bincount(codes, minlength=k).astype(float)

    def stat(xv: np.ndarray) -> float:
        ne = np.bincount(codes, weights=xv, minlength=k)
        nu = size - ne
        se = np.bincount(codes, weights=xv * y, minlength=k)
        su = np.bincount(codes, weights=y, minlength=k) - se
        w = ne * nu / size
        ok = (ne > 0) & (nu > 0)
        if not ok.any():
            return 0.0
        d = np.zeros(k)
        d[ok] = se[ok] / ne[ok] - su[ok] / nu[ok]
        return float((w * d).sum() / w.sum())

    obs = stat(x)
    count = 0
    for _ in range(n_perm):
        perm = np.lexsort((rng.random(len(x)), codes))
        if abs(stat(x[perm])) >= abs(obs) - 1e-12:
            count += 1
    return obs, (1 + count) / (1 + n_perm)


def exposure_effects(
    df: pd.DataFrame,
    exposure: str,
    min_exposed: int = 30,
    n_perm: int = 2000,
    seed: int = SEED,
    outcomes: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Compare exposed and unexposed PRs on each outcome (log scale) under models M1 to M3 and a permutation test.

    Effects are reported as the percentage difference in ``1 + outcome``.
    """
    rng = np.random.default_rng(seed)
    rows = []
    author_code = pd.factorize(df["author"])[0]
    base = df.assign(author_code=author_code, x=df[exposure].astype(int))
    for outcome, label in (outcomes or OUTCOMES).items():
        d = base.dropna(subset=[outcome]).copy()
        if outcome == "hours_to_merge":
            d = d[d["merged"]]
        d["y"] = np.log1p(d[outcome].astype(float).clip(lower=0))
        n_e = int(d["x"].sum())
        common = {
            "exposure": exposure, "outcome": outcome, "label": label,
            "n": len(d), "n_exposed": n_e,
            "median_exposed": float(d.loc[d["x"] == 1, outcome].median()) if n_e else np.nan,
            "median_unexposed": float(d.loc[d["x"] == 0, outcome].median()),
        }
        if n_e < min_exposed:
            rows.append({**common, "model": "all", "status": f"fewer than {min_exposed} exposed PRs"})
            continue
        # Labels are shuffled within author, so the null respects that exposure is clustered by person.
        strata = d["author_code"].to_numpy()
        obs, p_perm = _permutation_p(d["y"].to_numpy(), d["x"].to_numpy(), strata, n_perm, rng)
        for model, eff in (
            ("M1 month effects", _fit_month_fe(d, False)),
            ("M2 plus description length", _fit_month_fe(d, True)),
            ("M3 same author", _fit_author_fe(d)),
        ):
            row = {**common, "model": model, "status": "ok"}
            if eff is None:
                row["status"] = "too few authors with both kinds of PR"
            else:
                row.update(pct_difference=eff.pct, ci_low=eff.low, ci_high=eff.high, p=eff.p)
            if model.startswith("M2"):
                row["permutation_p"] = p_perm  # within-author shuffle
                row["permutation_stat_log"] = obs
            rows.append(row)
    out = pd.DataFrame(rows)
    if "p" in out:
        out["p_holm"] = np.nan
        for model, idx in out[out["status"] == "ok"].groupby("model").groups.items():
            out.loc[idx, "p_holm"] = holm(out.loc[idx, "p"].tolist())
    return out


@dataclass
class Verdict:
    category: str
    explanation: str
    pattern: str
    calls: dict


_WORDS = {
    "hours_to_merge": {"up": "slower", "down": "faster"},
}


def _word(outcome: str, direction: str) -> str:
    return _WORDS.get(outcome, {"up": "larger", "down": "smaller"})[direction]


def outcome_call(effects: pd.DataFrame, outcome: str) -> str:
    """"up", "down", "none" or "missing" under the plan's rule: M1 and M3 intervals both exclude zero, same sign."""
    e = effects[effects["outcome"] == outcome]
    m1 = e[e["model"] == "M1 month effects"]
    m3 = e[e["model"] == "M3 same author"]
    if m1.empty or m1.iloc[0]["status"] != "ok":
        return "missing"
    if m3.empty or m3.iloc[0]["status"] != "ok":
        return "no_within_author"
    r1, r3 = m1.iloc[0], m3.iloc[0]
    d1 = 1 if r1["ci_low"] > 0 else (-1 if r1["ci_high"] < 0 else 0)
    d3 = 1 if r3["ci_low"] > 0 else (-1 if r3["ci_high"] < 0 else 0)
    if d1 != 0 and d1 == d3:
        return "up" if d1 > 0 else "down"
    return "none"


def verdict(effects: pd.DataFrame) -> Verdict:
    """Apply the pre-specified verdict rule (see docs/ANALYSIS_PLAN.md) to one exposure's effects."""
    calls = {o: outcome_call(effects, o) for o in OUTCOMES}
    labels = {o: effects.loc[effects["outcome"] == o, "label"].iloc[0] for o in OUTCOMES if (effects["outcome"] == o).any()}

    def phrase(o: str) -> str:
        c = calls[o]
        return {"up": _word(o, "up"), "down": _word(o, "down"), "none": "no clear difference",
                "no_within_author": "no clear difference", "missing": "not estimated"}[c]

    pattern = "; ".join(f"{labels.get(o, o).lower()}: {phrase(o)}" for o in OUTCOMES)
    prim = calls[PRIMARY]
    if prim == "missing":
        return Verdict("not testable", "Too few exposed PRs.", pattern, calls)
    if prim == "no_within_author":
        return Verdict("not testable", "No author has both exposed and unexposed PRs, so the same-author check is impossible.",
                       pattern, calls)
    if prim in ("up", "down"):
        opposite = "down" if prim == "up" else "up"
        clash = [labels[o] for o in SIZE_SUPPORT if calls[o] == opposite]
        if clash:
            return Verdict("mixed", f"Lines changed is {_word(PRIMARY, prim)}, but {', '.join(clash).lower()} "
                           f"points the other way.", pattern, calls)
        return Verdict(_word(PRIMARY, prim), "Both the same-month and same-author intervals exclude zero and agree, "
                       "and no supporting size outcome contradicts them.", pattern, calls)
    m1 = effects[(effects["outcome"] == PRIMARY) & (effects["model"] == "M1 month effects")].iloc[0]
    sig1 = m1["ci_low"] > 0 or m1["ci_high"] < 0
    if sig1:
        return Verdict("no difference detected", "The same-month gap does not hold within the same author, so it "
                       "reflects who discloses AI use, not the PRs themselves.", pattern, calls)
    return Verdict("no difference detected", f"The same-month interval for lines changed runs from "
                   f"{m1['ci_low']:+.1f}% to {m1['ci_high']:+.1f}%.", pattern, calls)


def tool_robustness(df: pd.DataFrame, min_exposed: int = 30, n_perm: int = 200, seed: int = SEED) -> pd.DataFrame:
    """Lines-changed effect for each named tool against PRs with no disclosure. Robustness only, not part of the verdict."""
    rows = []
    for tool, n in df.loc[df["ai_disclosed"], "ai_tool"].value_counts().items():
        row = {"tool": tool, "n_exposed": int(n)}
        if n < min_exposed:
            rows.append({**row, "status": f"fewer than {min_exposed} exposed PRs"})
            continue
        sub = df[(df["ai_tool"] == tool) | (~df["ai_disclosed"])].copy()
        sub["x_tool"] = (sub["ai_tool"] == tool)
        eff = exposure_effects(sub, "x_tool", min_exposed, n_perm, seed, {PRIMARY: OUTCOMES[PRIMARY]})
        for tag, model in (("m1", "M1 month effects"), ("m3", "M3 same author")):
            r = eff[eff["model"] == model]
            if len(r) and r.iloc[0]["status"] == "ok":
                row.update({f"{tag}_pct": r.iloc[0]["pct_difference"], f"{tag}_low": r.iloc[0]["ci_low"],
                            f"{tag}_high": r.iloc[0]["ci_high"]})
        row["call"] = _word(PRIMARY, {"up": "up", "down": "down"}[outcome_call(eff, PRIMARY)]) \
            if outcome_call(eff, PRIMARY) in ("up", "down") else "no clear difference"
        row["status"] = "ok"
        rows.append(row)
    return pd.DataFrame(rows)
