"""Offline tests. No network access is used."""
import sys
from argparse import Namespace
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from prwords import signals, stats  # noqa: E402
from prwords.cli import analyse_repo, parse_args  # noqa: E402
from prwords.features import FeatureOptions, build_features, filter_authors  # noqa: E402
from prwords.fetch import fetch_file_lists, fetch_pull_requests  # noqa: E402
from prwords.filetypes import CATEGORIES, classify_path, file_check, select_sample  # noqa: E402
from prwords.labels import LabelClassifier  # noqa: E402
from prwords.text import (  # noqa: E402
    count_words, detect_templates_by_month, line_set, summarise_template_changes,
)
from synthetic import FakeClient, make_nodes  # noqa: E402

START, END = date(2025, 1, 6), date(2026, 8, 17)
FETCHED = datetime(2026, 11, 17, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def planted(tmp_path_factory):
    nodes = make_nodes(START, END, seed=1, ai_effect=-0.4)
    raw, fetched, lang = fetch_pull_requests(FakeClient(nodes), "o", "r", START, END, tmp_path_factory.mktemp("c"))
    assert lang == "Go"
    feat, audit, _ = build_features(filter_authors(raw), fetched, FeatureOptions(language=lang))
    return feat, audit


# ------------------------------------------------------------------ text --
def test_count_words():
    assert count_words("Fix the bug in parser") == 5
    assert count_words("don't split well-known words") == 4
    assert count_words("snake_case and 42") == 4
    assert count_words("") == 0


def test_line_set_drops_markup_and_checkbox_state():
    body = "<!-- note -->\n- [x] I read the guide\n```\ncode\n```\nSee http://a.b now"
    assert "i read the guide" in line_set(body)
    assert all("code" != l for l in line_set(body))


def test_monthly_template_detection_catches_mid_quarter_change(planted):
    feat, audit = planted
    changes = summarise_template_changes(audit)
    added = changes[changes["change_event"] == "added"]
    assert {"## performance impact", "## rollout plan"} <= set(added["line"])
    assert set(added["first_month"]) == {"2025-11"}
    # Template text is removed, so no description is inflated by it.
    assert feat["words_prose"].min() >= 0
    assert feat["words_raw"].mean() > feat["words_prose"].mean()


def test_small_samples_never_trigger_templates():
    months = pd.Series(["2025-01"] * 10)
    sets = pd.Series([["same line"]] * 10)
    tpl, audit = detect_templates_by_month(months, sets, 0.2, 30)
    assert tpl["2025-01"] == set() and audit.empty


# --------------------------------------------------------------- signals --
@pytest.mark.parametrize("text", [
    "Co-authored-by: Claude <noreply@anthropic.com>",
    "Co-authored-by: Copilot <x@y.z>",
    "Generated with Claude Code",
    "\U0001F916 Generated with Cursor",
    "Assisted-by: Codex:gpt-5",
    "I drafted this using ChatGPT and edited it",
    "This is AI-generated",
])
def test_ai_disclosure_positive(text):
    assert signals.find_ai_disclosure(text)


@pytest.mark.parametrize("text", [
    "Fix race in scheduler", "Co-authored-by: Jane Doe <jane@example.com>",
    "Co-authored-by: Alex Willmer <alex@example.com>",  # "llm" inside a name is not a tool
    "Adds an assistant interface to the kubelet", "",
])
def test_ai_disclosure_negative(text):
    assert signals.find_ai_disclosure(text) is None


# ---------------------------------------------------------------- labels --
def test_label_classifier():
    clf = LabelClassifier()
    c = clf.classify(["kind/bug", "kind/design", "size/XL", "area/docker"])
    assert c["bug"] and c["design"] and not c["docs"] and not c["feature"]
    assert clf.size_label(["size/XL"]) == "XL" and clf.has_kind_label(["kind/bug"])
    assert not clf.classify(["feature-gate"])["feature"]


# -------------------------------------------------------------- features --
def test_bots_and_weekly_cap():
    def row(n, day, author, typ="User"):
        return {"number": n, "created_at": pd.Timestamp(f"2025-01-{day}T10:00:00Z"), "author": author, "author_type": typ}
    df = pd.DataFrame([row(1, 6, "alice"), row(2, 7, "alice"), row(3, 8, "alice"), row(4, 8, "alice"),
                       row(5, 8, "dependabot[bot]"), row(6, 8, "ci-bot"), row(7, 8, "x", "Bot")])
    assert sorted(filter_authors(df)["number"]) == [1, 2, 3, 4]
    assert sorted(filter_authors(df, 3)["number"]) == [1, 2, 3]


def test_features_flow_and_follow_up(planted):
    feat, _ = planted
    assert feat["followup_ok"].all()
    merged = feat[feat["merged"]]
    assert merged["hours_to_merge"].notna().all() and (merged["hours_to_merge"] > 0).all()
    assert (feat["churn"] == feat["additions"] + feat["deletions"]).all()
    assert feat["ai_disclosed"].sum() > 100


# ----------------------------------------------------------------- stats --
def test_planted_smaller_effect_is_recovered(planted):
    feat, _ = planted
    eff = stats.exposure_effects(feat, "ai_disclosed", n_perm=300)
    row = eff[(eff["outcome"] == "churn") & (eff["model"] == "M1 month effects")].iloc[0]
    assert -45 < row["pct_difference"] < -20 and row["ci_high"] < 0
    m3 = eff[(eff["outcome"] == "churn") & (eff["model"] == "M3 same author")].iloc[0]
    assert m3["pct_difference"] < 0 and m3["ci_high"] < 0
    perm = eff[(eff["outcome"] == "churn") & (eff["model"] == "M2 plus description length")].iloc[0]
    assert perm["permutation_p"] < 0.01
    v = stats.verdict(eff)
    assert v.category == "smaller" and "lines changed: smaller" in v.pattern


def test_planted_larger_effect_is_recovered():
    nodes = make_nodes(START, END, seed=3, ai_effect=+0.5)
    raw, fetched, _ = fetch_pull_requests(FakeClient(nodes), "o", "r2", START, END, Path("/tmp/prwords_t_larger"))
    feat, _, _ = build_features(filter_authors(raw), fetched, FeatureOptions())
    eff = stats.exposure_effects(feat, "ai_disclosed", n_perm=100)
    assert stats.verdict(eff).category == "larger"


@pytest.mark.parametrize("seed", [5, 6, 7, 8, 9, 10])
def test_null_effect_calls_no_direction(seed, tmp_path):
    """Seed 5 produced a chance same-month difference, because the few disclosing authors happened to write
    bigger PRs. The same-author check must stop that being called a finding."""
    nodes = make_nodes(START, END, seed=seed, ai_effect=0.0)
    raw, fetched, _ = fetch_pull_requests(FakeClient(nodes), "o", "n", START, END, tmp_path)
    feat, _, _ = build_features(filter_authors(raw), fetched, FeatureOptions())
    eff = stats.exposure_effects(feat, "ai_disclosed", n_perm=300)
    assert stats.verdict(eff).category == "no difference detected"


def test_cache_survives_unicode_line_separators(tmp_path):
    """U+2028 inside a description is valid JSON. It broke cache reads when lines were split with splitlines()."""
    nodes = make_nodes(START, END, seed=1, ai_effect=0.0)[:5]
    nodes[0]["body"] += " second line \x85"
    raw, _, _ = fetch_pull_requests(FakeClient(nodes), "o", "u", START, END, tmp_path)
    again, _, _ = fetch_pull_requests(FakeClient([]), "o", "u", START, END, tmp_path)  # served from the cache
    assert len(raw) == len(again) == 5
    assert again["body"].str.contains(" ").any()


def test_template_audit_masks_email_addresses():
    """A repeated line naming a person's email is template text, but the published audit must not show it."""
    months = pd.Series(["2025-11"] * 40)
    sets = pd.Series([["author: jane.doe@example.com", f"change {i}"] for i in range(40)])
    templates, audit = detect_templates_by_month(months, sets, 0.2, 30)
    assert "author: jane.doe@example.com" in templates["2025-11"]  # still removed from word counts
    assert audit["line"].tolist() == ["author: <email>"]


def test_client_retries_a_body_that_is_not_json(monkeypatch):
    """GitHub sometimes answers 200 with an empty body after 502s. That must be retried, not crash the run."""
    import requests

    from prwords import fetch

    def response(status, body):
        r = requests.Response()
        r.status_code, r._content = status, body
        return r

    replies = iter([response(502, b""), response(200, b""), response(200, b'{"data": {"ok": 1}}')])
    client = fetch.GitHubGraphQL(token="t")
    monkeypatch.setattr(client.session, "post", lambda *a, **k: next(replies))
    monkeypatch.setattr(fetch.time, "sleep", lambda s: None)
    assert client.graphql("query", {}) == {"ok": 1}


def test_too_few_exposed_is_not_estimated(planted):
    feat, _ = planted
    eff = stats.exposure_effects(feat, "ai_disclosed", min_exposed=10**6, n_perm=10)
    assert (eff["status"] != "ok").all() and stats.verdict(eff).category == "not testable"


def test_window_tables_recover_planted_words_growth(planted):
    feat, _ = planted
    w = stats.window_numeric_table(feat, START, END, 28, n_boot=300).set_index("metric")
    r = w.loc["words_prose"]
    assert 2.0 < r["ratio"] < 3.6 and r["ratio_ci_low"] < r["ratio"] < r["ratio_ci_high"]
    assert r["mannwhitney_p"] < 1e-6
    assert abs(w.loc["churn", "ratio"] - 1) < 0.35  # size is flat by construction


def test_holm_is_monotone_and_bounded():
    adj = stats.holm([0.01, 0.04, 0.03, 0.5])
    assert adj[0] == pytest.approx(0.04) and max(adj) <= 1.0


def _eff_rows(spec):
    """spec: {outcome: (m1_low, m1_high, m3_low, m3_high)} as a hand-made effects table."""
    rows = []
    for outcome, (a, b, c, d) in spec.items():
        for model, lo, hi in (("M1 month effects", a, b), ("M3 same author", c, d)):
            rows.append({"exposure": "ai_disclosed", "outcome": outcome, "label": stats.OUTCOMES[outcome],
                         "model": model, "status": "ok", "ci_low": lo, "ci_high": hi,
                         "pct_difference": (lo + hi) / 2, "n_exposed": 100})
    return pd.DataFrame(rows)


NONE_SPEC = {o: (-5, 5, -5, 5) for o in stats.OUTCOMES}


def test_verdict_mixed_when_supporting_outcome_contradicts():
    spec = {**NONE_SPEC, "churn": (10, 40, 5, 30), "additions": (10, 40, 5, 30), "files_changed": (-40, -10, -30, -5)}
    v = stats.verdict(_eff_rows(spec))
    assert v.category == "mixed" and "files changed" in v.explanation.lower()


def test_verdict_larger_in_lines_with_same_files_is_not_mixed():
    spec = {**NONE_SPEC, "churn": (10, 40, 5, 30), "additions": (10, 40, 5, 30)}
    v = stats.verdict(_eff_rows(spec))
    assert v.category == "larger"
    assert "files changed: no clear difference" in v.pattern and "lines added: larger" in v.pattern


def test_verdict_needs_both_models_to_call():
    spec = {**NONE_SPEC, "churn": (10, 40, -5, 30)}  # M1 significant, M3 not
    v = stats.verdict(_eff_rows(spec))
    assert v.category == "no difference detected" and "who discloses" in v.explanation
    assert stats.verdict(_eff_rows({**NONE_SPEC, "churn": (10, 40, -40, -10)})).category == "no difference detected"


def test_time_to_merge_uses_speed_words():
    spec = {**NONE_SPEC, "churn": (10, 40, 5, 30), "hours_to_merge": (10, 40, 5, 30)}
    assert "hours to merge: slower" in stats.verdict(_eff_rows(spec)).pattern


def test_extract_tool():
    assert signals.extract_tool("Co-authored-by: Claude <noreply@anthropic.com>") == "claude"
    assert signals.extract_tool("Co-authored-by: Copilot <x>") == "copilot"
    assert signals.extract_tool("Assisted-by: Codex:gpt-5") == "codex"
    assert signals.extract_tool("assisted-by: somebot") == "unspecified"
    assert signals.extract_tool(None) is None


@pytest.mark.parametrize("path,cat", [
    ("pkg/kubelet/server.go", "code"), ("pkg/kubelet/server_test.go", "tests"), ("test/e2e/node/pod.go", "tests"),
    ("docs/guide.md", "docs"), ("README.md", "docs"), ("go.sum", "generated"), ("vendor/x/y.go", "generated"),
    ("staging/zz_generated.deepcopy.go", "generated"), ("api/openapi-spec/swagger.json", "generated"),
    ("deploy/app.yaml", "config"), (".github/workflows/ci.yml", "config"), ("logo.png", "other"),
])
def test_classify_path(path, cat):
    assert classify_path(path) == cat and cat in CATEGORIES


def test_tool_robustness_finds_both_tools(planted):
    feat, _ = planted
    t = stats.tool_robustness(feat, n_perm=50).set_index("tool")
    assert {"claude", "copilot"} <= set(t.index)
    assert (t.loc[["claude", "copilot"], "call"] == "smaller").all()


def test_file_check_recovers_effect_on_code_lines(planted, tmp_path):
    feat, _ = planted
    numbers = select_sample(feat, 300)
    exposed_in_sample = feat[feat["number"].isin(numbers)]["ai_disclosed"].sum()
    assert 30 <= exposed_in_sample <= 300
    nodes = make_nodes(START, END, seed=1, ai_effect=-0.4)
    files = fetch_file_lists(FakeClient(nodes), "o", "r", numbers, tmp_path)
    again = fetch_file_lists(FakeClient([]), "o", "r", numbers, tmp_path)  # served from the cache
    assert len(again) == len(files)
    res = file_check(feat, files)
    assert res["status"] == "ok" and res["effect"].pct < -15 and res["effect"].high < 0
    assert res["mix"][CATEGORIES].sum(axis=1).round(6).eq(1.0).all()


def test_rule_is_conservative_when_same_month_power_is_low(tmp_path):
    """A real 26% reduction with 284 exposed PRs goes uncalled, because the same-month check is noisy with
    few disclosing authors. The same-author estimate is tight and correct. This pins the intended behaviour:
    the report shows the intervals so a reader can see the effect that could not be confirmed."""
    nodes = make_nodes(START, END, seed=2, ai_effect=-0.3, per_day=8)
    raw, fetched, _ = fetch_pull_requests(FakeClient(nodes), "o", "low", START, END, tmp_path)
    feat, _, _ = build_features(filter_authors(raw), fetched, FeatureOptions())
    eff = stats.exposure_effects(feat, "ai_disclosed", n_perm=100, outcomes={"churn": "Lines changed"})
    v = stats.verdict(eff)
    m3 = eff[eff["model"] == "M3 same author"].iloc[0]
    assert v.category == "no difference detected" and m3["ci_high"] < 0


# ------------------------------------------------------- fetch and cache --
def test_fetch_window_resume_and_page_halving(tmp_path):
    nodes = make_nodes(date(2024, 12, 1), date(2025, 8, 30), per_day=6)
    client = FakeClient(nodes, fail_first_large=True)
    s, e = date(2025, 1, 6), date(2025, 6, 30)
    got, _, _ = fetch_pull_requests(client, "o", "r", s, e, tmp_path, page_size=50)
    assert min(client.page_sizes[1:]) <= 25 and 50 in client.page_sizes
    ts = got["created_at"].dt.date
    assert ts.min() >= s and ts.max() <= e
    calls = client.calls
    again, _, _ = fetch_pull_requests(client, "o", "r", s, e, tmp_path, page_size=50)
    assert client.calls == calls and len(again) == len(got)
    # Changing a setting discards the cache
    fetch_pull_requests(client, "o", "r", s, e, tmp_path, page_size=50, with_commit_messages=True)
    assert client.calls > calls


# ------------------------------------------------------------ end to end --
def test_full_run_writes_all_artifacts(tmp_path):
    nodes = make_nodes(START, END, seed=1, ai_effect=-0.4, per_day=12)
    args = parse_args(["demo/repo", "--n-boot", "200", "--n-perm", "100"])
    res = analyse_repo(FakeClient(nodes), "demo/repo", START, END, tmp_path / "out", tmp_path / "cache", args)
    d = tmp_path / "out" / "demo__repo"
    expected = ["report.md", "results.json", "pr_features.csv", "monthly_summary.csv", "template_audit.csv",
                "template_lines_summary.csv", "window_numeric.csv", "window_proportions.csv", "label_summary.csv",
                "exposure_effects.csv", "tool_robustness.csv", "file_type_sample.csv", "file_type_mix.csv",
                "ai_disclosure_samples.csv", "words_monthly.png", "size_monthly.png",
                "flow_monthly.png", "labels_monthly.png", "ai_signals_monthly.png", "effects.png"]
    for f in expected:
        assert (d / f).exists() and (d / f).stat().st_size > 0, f
    report = (d / "report.md").read_text()
    assert "Did the PR template change?" in report and "**Verdict:" in report and "Pattern:" in report
    assert "primary language: Go" in report and "File type check" in report
    assert res["language"] == "Go" and res["verdicts"]["ai_disclosed"].category == "smaller"
    assert "—" not in report and "–" not in report
