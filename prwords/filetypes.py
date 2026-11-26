"""File type check: is a larger PR larger because of code, or because of lockfiles, generated files and docs?"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from .stats import Effect, _fit_month_fe

CATEGORIES = ["code", "tests", "docs", "config", "generated", "other"]

_GENERATED = re.compile(
    r"(^|/)(vendor|third_party|node_modules|dist|build|generated)/|zz_generated|"
    r"\.pb\.(go|cc|h)$|_pb2(_grpc)?\.py$|\.min\.(js|css)$|\.snap$|"
    r"(^|/)(openapi|swagger)[^/]*\.json$|"
    r"(^|/)(go\.sum|go\.work\.sum|package-lock\.json|yarn\.lock|pnpm-lock\.yaml|cargo\.lock|poetry\.lock|"
    r"gemfile\.lock|composer\.lock|uv\.lock|pipfile\.lock)$"
)
_TESTS = re.compile(r"(^|/)(tests?|__tests__|testdata|e2e|spec)/|_test\.[a-z]+$|(^|/)test_[^/]*$|\.(test|spec)\.[jt]sx?$")
_DOCS = re.compile(r"\.(md|mdx|rst|txt|adoc)$|(^|/)(docs?|documentation)/|(^|/)(readme|changelog|license|notice|owners)[^/]*$")
_CONFIG = re.compile(
    r"\.(ya?ml|json|toml|ini|cfg|conf|env|properties|lock|mod)$|(^|/)(dockerfile|makefile|\.gitignore|codeowners)$|^\.github/"
)
_CODE_EXT = {
    "go", "py", "js", "jsx", "ts", "tsx", "java", "kt", "scala", "c", "h", "cc", "cpp", "hpp", "cs", "rs", "rb",
    "php", "swift", "m", "mm", "sh", "bash", "ps1", "sql", "lua", "pl", "r", "dart", "ex", "exs", "erl", "hs",
    "ml", "clj", "vue", "svelte", "html", "css", "scss", "less", "proto", "tf", "zig", "nim", "groovy", "gradle",
}


def classify_path(path: str) -> str:
    """Assign a changed file to one of CATEGORIES by its path. Order matters: generated wins over tests."""
    p = (path or "").lower()
    if _GENERATED.search(p):
        return "generated"
    if _TESTS.search(p):
        return "tests"
    if _DOCS.search(p):
        return "docs"
    if _CONFIG.search(p):
        return "config"
    ext = p.rsplit(".", 1)[-1] if "." in p.rsplit("/", 1)[-1] else ""
    return "code" if ext in _CODE_EXT else "other"


def select_sample(feat: pd.DataFrame, n_exposed: int, seed: int = 42, exposure: str = "ai_disclosed") -> list[int]:
    """Up to ``n_exposed`` exposed PRs plus unexposed PRs from the same months, in equal numbers per month."""
    rng = np.random.default_rng(seed)
    exposed = feat[feat[exposure]]
    if len(exposed) > n_exposed:
        exposed = exposed.sample(n_exposed, random_state=seed)
    picks = list(exposed["number"])
    pool = feat[~feat[exposure]]
    for month, k in exposed.groupby("month").size().items():
        cand = pool[pool["month"] == month]["number"].to_numpy()
        if len(cand):
            picks.extend(rng.choice(cand, size=min(k, len(cand)), replace=False).tolist())
    return [int(x) for x in picks]


def summarise_files(files: pd.DataFrame) -> pd.DataFrame:
    """One row per PR: changed lines per file category, plus ``code_test_lines`` and a truncation flag."""
    f = files.dropna(subset=["path"]).copy()
    f["category"] = f["path"].map(classify_path)
    f["lines"] = f["additions"] + f["deletions"]
    wide = f.pivot_table(index="number", columns="category", values="lines", aggfunc="sum", fill_value=0)
    for c in CATEGORIES:
        if c not in wide:
            wide[c] = 0
    wide = wide[CATEGORIES].add_prefix("lines_")
    wide["code_test_lines"] = wide["lines_code"] + wide["lines_tests"]
    wide["listed_lines"] = wide[[f"lines_{c}" for c in CATEGORIES]].sum(axis=1)
    trunc = files.groupby("number")["truncated"].first()
    out = wide.join(trunc, how="outer").fillna(0).reset_index()
    out["truncated"] = out["truncated"].astype(bool)
    return out


def file_check(feat: pd.DataFrame, files: pd.DataFrame, min_exposed: int = 30, exposure: str = "ai_disclosed") -> dict:
    """Line mix by file type for exposed and unexposed PRs, and the effect on code and test lines.

    PRs with more than 100 changed files are excluded because only 100 files are listed.
    """
    per_pr = summarise_files(files)
    d = feat.merge(per_pr, on="number", how="inner")
    n_trunc = int(d["truncated"].sum())
    d = d[~d["truncated"]].copy()
    d["x"] = d[exposure].astype(int)
    result: dict = {"n_exposed": int(d["x"].sum()), "n_unexposed": int((1 - d["x"]).sum()), "n_truncated_excluded": n_trunc}
    mix = []
    for label, g in (("exposed", d[d["x"] == 1]), ("unexposed", d[d["x"] == 0])):
        total = g[[f"lines_{c}" for c in CATEGORIES]].sum()
        share = total / total.sum() if total.sum() else total
        mix.append({"group": label, "n_prs": len(g), **{c: float(share[f"lines_{c}"]) for c in CATEGORIES},
                    "median_code_test_lines": float(g["code_test_lines"].median()) if len(g) else np.nan})
    result["mix"] = pd.DataFrame(mix)
    if result["n_exposed"] < min_exposed:
        result["effect"] = None
        result["status"] = f"fewer than {min_exposed} exposed PRs in the sample"
        return result
    d["author_code"] = pd.factorize(d["author"])[0]
    d["y"] = np.log1p(d["code_test_lines"].astype(float))
    result["effect"] = _fit_month_fe(d, with_length=False)
    result["status"] = "ok"
    return result
