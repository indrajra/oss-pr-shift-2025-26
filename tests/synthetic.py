"""Synthetic GraphQL data with planted effects, used by the offline tests and for demos."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import numpy as np

TEMPLATE_A = "## What this PR does\n- [ ] I have added tests\n"
TEMPLATE_B = TEMPLATE_A + "## Performance impact\n## Rollout plan\n"
TEMPLATE_CHANGE = date(2025, 11, 1)


def make_nodes(
    start: date,
    end: date,
    seed: int = 1,
    ai_effect: float = -0.4,
    per_day: int = 12,
    n_authors: int = 150,
    words_start: float = 20.0,
    words_end: float = 60.0,
) -> list[dict]:
    """PRs as GraphQL nodes. Disclosed PRs have lines changed scaled by exp(ai_effect).

    Description length rises from ``words_start`` to ``words_end``. Each author has a personal size
    level, and a fifth of authors disclose AI use on about 30% of their PRs.
    """
    rng = np.random.default_rng(seed)
    rng_tool = np.random.default_rng(seed + 1000)  # separate stream so tool choice never shifts the main draws
    author_level = rng.normal(0, 0.6, n_authors)
    ai_users = set(rng.choice(n_authors, n_authors // 5, replace=False).tolist())
    days = (end - start).days
    nodes, n = [], 0
    for d in range(days + 1):
        day = start + timedelta(days=d)
        level = words_start + (words_end - words_start) * d / days
        for _ in range(per_day):
            n += 1
            a = int(rng.integers(0, n_authors))
            disclosed = a in ai_users and rng.random() < 0.30
            churn = max(1, int(np.exp(np.log(60) + author_level[a] + ai_effect * disclosed + rng.normal(0, 0.9))))
            adds = int(churn * 0.7)
            words = max(1, int(rng.lognormal(np.log(level), 0.5)))
            body_words = " ".join(f"w{n}x{i}" for i in range(words))
            if rng.random() < 0.25:
                body_words += " the change is quietly sound"
            if rng.random() < 0.20:
                body_words += " it works — mostly"
            body = (TEMPLATE_B if day >= TEMPLATE_CHANGE else TEMPLATE_A) + body_words
            if disclosed:
                if rng_tool.random() < 0.7:
                    body += "\nCo-authored-by: Claude <noreply@anthropic.com>"
                else:
                    body += "\nCo-authored-by: Copilot <copilot@github.com>"
            created = datetime(day.year, day.month, day.day, int(rng.integers(0, 24)), tzinfo=timezone.utc)
            r = rng.random()
            merged = r < 0.75
            closed = (r < 0.9) and not merged
            ttm = float(rng.lognormal(np.log(48), 0.8))
            labels = []
            for name, p in (("kind/bug", 0.25), ("kind/feature", 0.15), ("kind/documentation", 0.08),
                            ("kind/design", 0.03), ("kind/cleanup", 0.10)):
                if rng.random() < p:
                    labels.append(name)
            labels.append("size/S" if churn < 100 else "size/L")
            fmt = lambda t: t.strftime("%Y-%m-%dT%H:%M:%SZ")
            nodes.append(
                {
                    "number": n,
                    "createdAt": fmt(created),
                    "closedAt": fmt(created + timedelta(hours=ttm)) if merged or closed else None,
                    "mergedAt": fmt(created + timedelta(hours=ttm)) if merged else None,
                    "state": "MERGED" if merged else ("CLOSED" if closed else "OPEN"),
                    "merged": merged,
                    "isDraft": bool(rng.random() < 0.05),
                    "body": body,
                    "additions": adds,
                    "deletions": churn - adds,
                    "changedFiles": max(1, int(np.sqrt(churn) / 2)),
                    "authorAssociation": "MEMBER" if a % 3 == 0 else "NONE",
                    "author": {"login": f"user{a}", "__typename": "User"},
                    "labels": {"nodes": [{"name": l} for l in labels]},
                    "comments": {"totalCount": int(rng.poisson(3))},
                    "reviews": {"totalCount": int(rng.poisson(2))},
                    "commits": {"totalCount": int(rng.integers(1, 6))},
                }
            )
    return nodes


class FakeClient:
    """Serves nodes newest first in pages, mimicking the GraphQL shape and cursor paging."""

    def __init__(self, nodes: list[dict], fail_first_large: bool = False):
        self.nodes = sorted(nodes, key=lambda x: x["createdAt"], reverse=True)
        self.calls = 0
        self.page_sizes: list[int] = []
        self.fail_first_large = fail_first_large

    def _files(self, number):
        node = next(n for n in self.nodes if n["number"] == number)
        churn = node["additions"] + node["deletions"]
        parts = [("pkg/mod.go", 0.60), ("pkg/mod_test.go", 0.20), ("docs/guide.md", 0.05), ("go.sum", 0.15)]
        files = []
        for path, share in parts:
            lines = int(churn * share)
            files.append({"path": path, "additions": int(lines * 0.7), "deletions": lines - int(lines * 0.7)})
        return {"repository": {"pullRequest": {"files": {"pageInfo": {"hasNextPage": False}, "nodes": files}}}}

    def graphql(self, query, variables):
        from prwords.fetch import GraphQLError

        if "pullRequest(number" in query:
            self.calls += 1
            return self._files(variables["number"])
        self.calls += 1
        size = variables["pageSize"]
        self.page_sizes.append(size)
        if self.fail_first_large and size > 25:
            raise GraphQLError("timeout")
        i = int(variables["cursor"] or 0)
        page = self.nodes[i : i + size]
        nxt = i + size
        return {
            "rateLimit": {"remaining": 4000, "resetAt": "2030-01-01T00:00:00Z", "cost": 1},
            "repository": {"primaryLanguage": {"name": "Go"}, "pullRequests": {
                "pageInfo": {"hasNextPage": nxt < len(self.nodes), "endCursor": str(nxt)},
                "nodes": page,
            }},
        }
