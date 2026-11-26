"""Word counting, markup removal and PR template detection."""
from __future__ import annotations

import re
from collections import Counter

import numpy as np
import pandas as pd

_HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
_FENCED = re.compile(r"(```|~~~).*?\1", re.S)
_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_URL = re.compile(r"https?://\S+")
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_HTML_TAG = re.compile(r"<[^>]+>")
_LIST_MARKER = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s*(?:\[[ xX]\]\s*)?")
_WORD = re.compile(r"[^\W_]+(?:['’\-][^\W_]+)*", re.UNICODE)


def count_words(text: str) -> int:
    """Count word tokens: letters or digits with optional internal hyphens or apostrophes."""
    return len(_WORD.findall(text))


def strip_markup(text: str) -> str:
    """Remove non-prose content (comments, code fences, images, URLs, tags), keeping line breaks."""
    text = _HTML_COMMENT.sub("\n", text)
    text = _FENCED.sub("\n", text)
    text = _IMAGE.sub(" ", text)
    text = _LINK.sub(r"\1", text)
    text = _URL.sub(" ", text)
    return _HTML_TAG.sub(" ", text)


def normalise_line(line: str) -> str:
    """Lowercase, drop list markers and checkbox state, collapse whitespace."""
    line = _LIST_MARKER.sub("", line.strip().lower())
    return re.sub(r"\s+", " ", line)


def line_set(body: str) -> list[str]:
    """Normalised, non-empty prose lines of a body."""
    return [n for n in (normalise_line(l) for l in strip_markup(body).splitlines()) if n]


def detect_templates_by_month(
    months: pd.Series,
    line_sets: pd.Series,
    min_share: float = 0.20,
    min_docs: int = 30,
) -> tuple[dict[str, set[str]], pd.DataFrame]:
    """Find template lines for each calendar month.

    A line is template text when it appears in at least ``min_share`` of the month's descriptions
    and at least ``min_docs`` of them. A month with fewer than ``min_docs`` PRs is pooled with the
    month before it. Detecting per month means a template edited mid-quarter is still removed.

    Returns ``(templates, audit)``. ``templates`` maps month to its template lines. ``audit`` has one
    row per (month, line) with the share of that month's PRs containing it.
    """
    order = sorted(months.unique())
    unique_sets = line_sets.map(lambda xs: set(xs))
    templates: dict[str, set[str]] = {}
    rows = []
    for i, month in enumerate(order):
        pool_months = [month]
        n = int((months == month).sum())
        if n < min_docs and i > 0:
            pool_months.insert(0, order[i - 1])
        mask = months.isin(pool_months)
        n_pool = int(mask.sum())
        if n_pool < min_docs:
            templates[month] = set()
            continue
        counts: Counter[str] = Counter()
        for s in unique_sets[mask]:
            counts.update(s)
        threshold = max(min_docs, int(np.ceil(min_share * n_pool)))
        found = {line for line, c in counts.items() if c >= threshold}
        templates[month] = found
        # The audit is published, so email addresses in repeated lines are masked there.
        rows.extend(
            {"month": month, "line": _EMAIL.sub("<email>", line), "share_of_prs": counts[line] / n_pool,
             "n_prs": n_pool}
            for line in found
        )
    audit = pd.DataFrame(rows, columns=["month", "line", "share_of_prs", "n_prs"])
    return templates, audit


def summarise_template_changes(audit: pd.DataFrame, min_peak_share: float = 0.5) -> pd.DataFrame:
    """One row per template line with its first and last month and peak share.

    A line whose first month is after the first month of the window, and which reaches at least
    ``min_peak_share``, marks a template change.
    """
    if audit.empty:
        return pd.DataFrame(columns=["line", "first_month", "last_month", "months", "peak_share", "change_event"])
    g = audit.groupby("line")
    out = g.agg(
        first_month=("month", "min"),
        last_month=("month", "max"),
        months=("month", "nunique"),
        peak_share=("share_of_prs", "max"),
    ).reset_index()
    window_first = audit["month"].min()
    window_last = audit["month"].max()
    out["change_event"] = np.select(
        [
            (out["first_month"] > window_first) & (out["peak_share"] >= min_peak_share),
            (out["last_month"] < window_last) & (out["peak_share"] >= min_peak_share),
        ],
        ["added", "removed"],
        default="",
    )
    return out.sort_values(["first_month", "peak_share"], ascending=[True, False]).reset_index(drop=True)


def add_word_counts(
    df: pd.DataFrame, min_share: float = 0.20, min_docs: int = 30
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Add ``month``, ``words_raw`` and ``words_prose``. Returns the frame and the template audit."""
    out = df.copy()
    out["month"] = out["created_at"].dt.tz_convert(None).dt.to_period("M").astype(str)
    out["words_raw"] = out["body"].map(count_words)
    sets = out["body"].map(line_set)
    templates, audit = detect_templates_by_month(out["month"], sets, min_share, min_docs)

    prose = []
    for month, lines in zip(out["month"], sets):
        tpl = templates.get(month, set())
        prose.append(count_words(" ".join(l for l in lines if l not in tpl)))
    out["words_prose"] = prose
    return out, audit
