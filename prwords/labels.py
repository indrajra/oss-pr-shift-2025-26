"""Map free-form repository labels onto a small set of comparable categories.

Labels are repository specific. The defaults cover Kubernetes style labels (``kind/bug``,
``kind/feature``, ``kind/design``) and common conventions elsewhere. Override them with
``--label-map FILE``, a JSON object of ``{"category": ["regex", ...]}``, matched case-insensitively
against each label name. A PR can belong to more than one category.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

DEFAULT_CATEGORIES: dict[str, list[str]] = {
    "feature": [
        r"^kind/feature$",
        r"^(?:type[:/ ]\s*)?(?:feature|enhancement|feat)$",
        r"^(?:feature|feat)[:/ ]",
        r"^new[- ]feature$",
    ],
    "bug": [
        r"^kind/bug$",
        r"^kind/regression$",
        r"^(?:type[:/ ]\s*)?(?:bug|bugfix|fix)$",
        r"^(?:bug|fix)[:/ ]",
    ],
    "design": [r"\bdesign\b"],
    "docs": [r"\bdocs?\b", r"documentation"],
    "cleanup": [r"^kind/cleanup$", r"\brefactor", r"^chore", r"maintenance"],
    "test": [r"flake", r"failing-test", r"^(?:kind/)?tests?$", r"^area/test"],
    "api_change": [r"api[-_ ]change"],
}

# "any kind label" is used to report label coverage, because bots change what gets labelled.
KIND_LABEL = re.compile(r"^(?:kind/|type[:/ ]|type-)", re.I)
SIZE_LABEL = re.compile(r"^size/(XXS|XS|S|M|L|XL|XXL)$", re.I)
SIZE_ORDER = ["XXS", "XS", "S", "M", "L", "XL", "XXL"]


def load_categories(path: Path | None) -> dict[str, list[str]]:
    if path is None:
        return DEFAULT_CATEGORIES
    return json.loads(Path(path).read_text(encoding="utf-8"))


class LabelClassifier:
    def __init__(self, categories: dict[str, list[str]] | None = None) -> None:
        cats = categories or DEFAULT_CATEGORIES
        self.patterns = {c: [re.compile(p, re.I) for p in pats] for c, pats in cats.items()}

    @property
    def categories(self) -> list[str]:
        return list(self.patterns)

    def classify(self, labels: list[str]) -> dict[str, bool]:
        out = {c: False for c in self.patterns}
        for label in labels:
            for cat, pats in self.patterns.items():
                if not out[cat] and any(p.search(label) for p in pats):
                    out[cat] = True
        return out

    @staticmethod
    def has_kind_label(labels: list[str]) -> bool:
        return any(KIND_LABEL.search(l) for l in labels)

    @staticmethod
    def size_label(labels: list[str]) -> str | None:
        for label in labels:
            m = SIZE_LABEL.match(label)
            if m:
                return m.group(1).upper()
        return None
