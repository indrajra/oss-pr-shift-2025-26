"""GitHub GraphQL collection with a resumable on-disk cache."""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol

import pandas as pd
import requests

from . import __version__
from .signals import find_ai_disclosure

log = logging.getLogger("prwords")

GRAPHQL_URL = "https://api.github.com/graphql"
SCHEMA_VERSION = 2
MIN_PAGE_SIZE = 10


def build_query(with_commit_messages: bool) -> str:
    commits = (
        "commits(first: 50) { totalCount nodes { commit { message } } }"
        if with_commit_messages
        else "commits { totalCount }"
    )
    return f"""
query($owner: String!, $name: String!, $cursor: String, $pageSize: Int!) {{
  rateLimit {{ remaining resetAt cost }}
  repository(owner: $owner, name: $name) {{
    primaryLanguage {{ name }}
    pullRequests(first: $pageSize, after: $cursor,
                 orderBy: {{field: CREATED_AT, direction: DESC}}) {{
      pageInfo {{ hasNextPage endCursor }}
      nodes {{
        number createdAt closedAt mergedAt state merged isDraft body
        additions deletions changedFiles authorAssociation
        author {{ login __typename }}
        labels(first: 30) {{ nodes {{ name }} }}
        comments {{ totalCount }}
        reviews {{ totalCount }}
        {commits}
      }}
    }}
  }}
}}
"""


class GraphQLClient(Protocol):
    def graphql(self, query: str, variables: dict) -> dict: ...


class GitHubGraphQL:
    """Minimal GitHub GraphQL client with retry and rate limit handling."""

    def __init__(self, token: str | None = None, max_retries: int = 6) -> None:
        token = token or os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if not token:
            raise SystemExit("Set GH_TOKEN or GITHUB_TOKEN to a GitHub access token.")
        self.session = requests.Session()
        self.session.headers.update(
            {"Authorization": f"bearer {token}", "User-Agent": f"prwords/{__version__}"}
        )
        self.max_retries = max_retries

    def graphql(self, query: str, variables: dict) -> dict:
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.session.post(
                    GRAPHQL_URL, json={"query": query, "variables": variables}, timeout=90
                )
            except requests.RequestException as exc:
                self._backoff(attempt, f"network error: {exc}")
                continue
            if resp.status_code in (502, 503, 504):
                self._backoff(attempt, f"HTTP {resp.status_code}")
                continue
            if resp.status_code in (403, 429) and "retry-after" in resp.headers:
                time.sleep(int(resp.headers["retry-after"]) + 1)
                continue
            resp.raise_for_status()
            try:
                payload = resp.json()
            except ValueError:
                # GitHub occasionally answers 200 with an empty or HTML body, usually after 502s.
                self._backoff(attempt, f"HTTP {resp.status_code} with a body that is not JSON")
                continue
            if "errors" in payload and not payload.get("data"):
                raise GraphQLError(str(payload["errors"]))
            self._respect_rate_limit(payload.get("data") or {})
            return payload["data"]
        raise GraphQLError("GitHub API kept failing after retries (timeouts or server errors)")

    @staticmethod
    def _backoff(attempt: int, why: str) -> None:
        delay = min(2 ** attempt, 60)
        log.warning("%s, retrying in %ss", why, delay)
        time.sleep(delay)

    @staticmethod
    def _respect_rate_limit(data: dict) -> None:
        rl = data.get("rateLimit")
        if rl and rl["remaining"] < 25:
            reset = datetime.fromisoformat(rl["resetAt"].replace("Z", "+00:00"))
            wait = max((reset - datetime.now(timezone.utc)).total_seconds(), 0) + 5
            log.info("Rate limit nearly exhausted, sleeping %.0fs", wait)
            time.sleep(wait)


class GraphQLError(RuntimeError):
    pass


def _ts(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def _record(node: dict, with_commit_messages: bool) -> dict:
    author = node.get("author") or {}
    commit_match = None
    if with_commit_messages:
        for n in (node.get("commits") or {}).get("nodes") or []:
            commit_match = find_ai_disclosure((n.get("commit") or {}).get("message") or "")
            if commit_match:
                break
    return {
        "number": node["number"],
        "created_at": node["createdAt"],
        "closed_at": node.get("closedAt"),
        "merged_at": node.get("mergedAt"),
        "state": node.get("state"),
        "merged": bool(node.get("merged")),
        "is_draft": bool(node.get("isDraft")),
        "body": node.get("body") or "",
        "additions": node.get("additions"),
        "deletions": node.get("deletions"),
        "changed_files": node.get("changedFiles"),
        "association": node.get("authorAssociation"),
        "author": author.get("login") or "ghost",
        "author_type": author.get("__typename") or "User",
        "labels": [l["name"] for l in (node.get("labels") or {}).get("nodes") or []],
        "comments": (node.get("comments") or {}).get("totalCount"),
        "reviews": (node.get("reviews") or {}).get("totalCount"),
        "commits": (node.get("commits") or {}).get("totalCount"),
        "ai_commit_match": commit_match,
    }


def fetch_pull_requests(
    client: GraphQLClient,
    owner: str,
    name: str,
    start: date,
    end: date,
    cache_dir: Path,
    page_size: int = 50,
    with_commit_messages: bool = False,
) -> tuple[pd.DataFrame, datetime, str | None]:
    """Return all PRs created in [start, end] (UTC, inclusive), the time the fetch finished and the
    repository's primary language.

    Pages newest first and stops once it passes ``start``. Progress is written to
    ``<cache_dir>/<owner>__<name>.jsonl`` with a sidecar state file, so an interrupted run resumes
    from the last completed page. If the API times out the page size is halved automatically.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{owner}__{name}"
    data_path = cache_dir / f"{stem}.jsonl"
    state_path = cache_dir / f"{stem}.state.json"
    key = {
        "schema": SCHEMA_VERSION,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "commit_messages": with_commit_messages,
    }

    state = {"cursor": None, "done": False, "key": key, "page_size": page_size, "fetched_at": None,
             "language": None}
    if state_path.exists() and data_path.exists():
        saved = json.loads(state_path.read_text())
        if saved.get("key") == key:
            state = saved
            log.info("Resuming %s (done=%s)", stem, state["done"])
        else:
            log.info("Cache settings changed, discarding cache for %s", stem)
            data_path.unlink()

    lo = datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc)
    hi = datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
    query = build_query(with_commit_messages)

    if not state["done"]:
        pages = 0
        with data_path.open("a", encoding="utf-8") as fh:
            while True:
                try:
                    data = client.graphql(
                        query,
                        {"owner": owner, "name": name, "cursor": state["cursor"],
                         "pageSize": state["page_size"]},
                    )
                except GraphQLError as exc:
                    if state["page_size"] <= MIN_PAGE_SIZE:
                        raise
                    state["page_size"] = max(MIN_PAGE_SIZE, state["page_size"] // 2)
                    log.warning("%s, reducing page size to %d", exc, state["page_size"])
                    continue
                conn = data["repository"]["pullRequests"]
                state["language"] = (data["repository"].get("primaryLanguage") or {}).get("name")
                reached_start = False
                for node in conn["nodes"]:
                    created = _ts(node["createdAt"])
                    if created < lo:
                        reached_start = True
                        continue
                    if created >= hi:
                        continue
                    fh.write(json.dumps(_record(node, with_commit_messages), ensure_ascii=False) + "\n")
                fh.flush()
                pages += 1
                state["cursor"] = conn["pageInfo"]["endCursor"]
                state["done"] = reached_start or not conn["pageInfo"]["hasNextPage"]
                if state["done"]:
                    state["fetched_at"] = datetime.now(timezone.utc).isoformat()
                state_path.write_text(json.dumps(state))
                if pages % 20 == 0:
                    log.info("%s: %d pages fetched", stem, pages)
                if state["done"]:
                    break

    # Split on "\n" only: bodies are written with ensure_ascii=False, and splitlines() would also
    # break records at characters such as U+2028 that are valid inside a JSON string.
    text = data_path.read_text(encoding="utf-8")
    rows = [json.loads(line) for line in text.split("\n") if line]
    fetched_at = datetime.fromisoformat(state["fetched_at"])
    df = pd.DataFrame(rows)
    language = state.get("language")
    if df.empty:
        return df, fetched_at, language
    for col in ("created_at", "closed_at", "merged_at"):
        df[col] = pd.to_datetime(df[col], utc=True)
    df = df.drop_duplicates("number").sort_values("created_at").reset_index(drop=True)
    return df, fetched_at, language


FILES_QUERY = """
query($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      files(first: 100) {
        pageInfo { hasNextPage }
        nodes { path additions deletions }
      }
    }
  }
}
"""


def fetch_file_lists(
    client: GraphQLClient, owner: str, name: str, numbers: list[int], cache_dir: Path
) -> pd.DataFrame:
    """Changed files for the given PR numbers: one row per file, cached and resumable.

    Only the first 100 files of a PR are listed. ``truncated`` marks PRs with more.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{owner}__{name}.files.jsonl"
    done: set[int] = set()
    if path.exists():
        done = {json.loads(l)["number"] for l in path.read_text(encoding="utf-8").splitlines()}
    todo = [n for n in numbers if n not in done]
    with path.open("a", encoding="utf-8") as fh:
        for i, number in enumerate(todo, 1):
            data = client.graphql(FILES_QUERY, {"owner": owner, "name": name, "number": int(number)})
            pr = (data.get("repository") or {}).get("pullRequest") or {}
            files = pr.get("files") or {}
            fh.write(json.dumps({
                "number": int(number),
                "truncated": bool((files.get("pageInfo") or {}).get("hasNextPage")),
                "files": files.get("nodes") or [],
            }) + "\n")
            if i % 100 == 0:
                fh.flush()
                log.info("%s: file lists fetched for %d of %d PRs", f"{owner}/{name}", i, len(todo))
    wanted = set(numbers)
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        if rec["number"] not in wanted:
            continue
        for f in rec["files"]:
            rows.append({"number": rec["number"], "truncated": rec["truncated"], "path": f["path"],
                         "additions": f["additions"], "deletions": f["deletions"]})
        if not rec["files"]:
            rows.append({"number": rec["number"], "truncated": rec["truncated"], "path": None,
                         "additions": 0, "deletions": 0})
    return pd.DataFrame(rows, columns=["number", "truncated", "path", "additions", "deletions"])
