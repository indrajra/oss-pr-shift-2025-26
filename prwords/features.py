"""Turn raw PR records into one analysis row per pull request."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from . import signals
from .labels import LabelClassifier, load_categories
from .text import add_word_counts, count_words, strip_markup

_BOT_NAME = re.compile(r"(\[bot\]$|-bot$|^copilot$|^dependabot|^renovate|-robot$)", re.I)
INSIDER_ASSOCIATIONS = {"OWNER", "MEMBER", "COLLABORATOR"}


@dataclass
class FeatureOptions:
    author_weekly_cap: int | None = None
    template_share: float = 0.20
    template_min_docs: int = 30
    followup_days: int = 30
    label_map: Path | None = None
    language: str | None = None
    extra: dict = field(default_factory=dict)


def is_bot(login: str, author_type: str) -> bool:
    return author_type == "Bot" or bool(_BOT_NAME.search(login or ""))


def filter_authors(df: pd.DataFrame, weekly_cap: int | None = None) -> pd.DataFrame:
    """Remove bot accounts and optionally cap PRs per author per ISO week."""
    keep = ~df.apply(lambda r: is_bot(r["author"], r["author_type"]), axis=1)
    out = df[keep].copy()
    if weekly_cap:
        week = out["created_at"].dt.strftime("%G-W%V")
        rank = out.groupby([out["author"], week]).cumcount()
        out = out[rank < weekly_cap]
    return out.reset_index(drop=True)


def _normalised_text(body: str) -> str:
    return " ".join(re.findall(r"[^\W_]+", strip_markup(body).lower()))


def build_features(
    df: pd.DataFrame, fetched_at: datetime, opts: FeatureOptions
) -> tuple[pd.DataFrame, pd.DataFrame, LabelClassifier]:
    """Return ``(features, template_audit, label_classifier)``."""
    out, audit = add_word_counts(df, opts.template_share, opts.template_min_docs)

    # Size and flow
    for col in ("additions", "deletions", "changed_files", "comments", "reviews", "commits"):
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.rename(columns={"changed_files": "files_changed"})
    out["net_lines"] = out["additions"] - out["deletions"]
    out["churn"] = out["additions"] + out["deletions"]
    out["hours_to_merge"] = np.where(
        out["merged"], (out["merged_at"] - out["created_at"]).dt.total_seconds() / 3600, np.nan
    )
    out["closed_unmerged"] = (out["state"] == "CLOSED") & ~out["merged"]
    out["is_open"] = out["state"] == "OPEN"
    horizon = timedelta(days=opts.followup_days)
    eligible = (out["created_at"] + horizon) <= pd.Timestamp(fetched_at)
    out["followup_ok"] = eligible
    out["merged_in_followup"] = np.where(
        eligible, out["merged"] & (out["hours_to_merge"] <= opts.followup_days * 24), np.nan
    )

    # People
    out["is_outside"] = ~out["association"].isin(INSIDER_ASSOCIATIONS)

    # Labels
    clf = LabelClassifier(load_categories(opts.label_map))
    cats = pd.DataFrame([clf.classify(l) for l in out["labels"]], index=out.index)
    cats.columns = [f"cat_{c}" for c in cats.columns]
    out = pd.concat([out, cats], axis=1)
    out["has_kind_label"] = out["labels"].map(clf.has_kind_label)
    out["size_label"] = out["labels"].map(clf.size_label)

    # AI disclosure
    body_match = out["body"].map(signals.find_ai_disclosure)
    commit_match = out["ai_commit_match"] if "ai_commit_match" in out else pd.Series(None, index=out.index)
    out["ai_match"] = body_match.where(body_match.notna(), commit_match)
    out["ai_disclosed"] = out["ai_match"].notna()
    out["ai_tool"] = out["ai_match"].map(signals.extract_tool)
    out["repo_language"] = opts.language

    # Repeated text
    key = out["body"].map(_normalised_text)
    long_enough = key.str.split().str.len() >= 10
    counts = key.where(long_enough).map(key.where(long_enough).value_counts())
    out["is_duplicate_text"] = counts.fillna(0) >= 2

    return out, audit, clf
