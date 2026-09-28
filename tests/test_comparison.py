from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from deadtrace.analysis import analyze
from deadtrace.artifacts import ArtifactError, read_json_artifact, render_json_artifact
from deadtrace.baseline import (
    apply_baseline,
    create_baseline,
    update_baseline,
    validate_baseline,
)
from deadtrace.comparison import (
    Comparability,
    compare_reports,
    render_comparison_json,
    render_comparison_text,
    validate_semantic_report,
)
from deadtrace.config import Config
from deadtrace.semantic_report import semantic_report_dict


def _source(*extra: str) -> str:
    return """
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def live() -> None:
    pass

def existing_candidate() -> None:
    pass
""" + "\n".join(extra)


def _report(tmp_path: Path, source: str, config: Config | None = None) -> dict[str, Any]:
    (tmp_path / "main.py").write_text(source, encoding="utf-8")
    return semantic_report_dict(analyze(tmp_path, config or Config()))


def test_report_comparison_tracks_added_resolved_and_unchanged(tmp_path: Path) -> None:
    before = _report(tmp_path, _source())
    after = _report(tmp_path, _source("def new_candidate() -> None:\n    pass\n"))

    comparison = compare_reports(before, after)

    assert comparison.status is Comparability.COMPARABLE
    assert {item["title"] for item in comparison.added} == {"Unreached component: new_candidate"}
    assert len(comparison.unchanged) == 1
    assert not comparison.resolved
    assert '"comparability": "comparable"' in render_comparison_json(comparison)
    assert "Added: 1" in render_comparison_text(comparison)

    final = _report(tmp_path, _source().replace("def existing_candidate", "def used"))
    resolved = compare_reports(after, final)
    assert len(resolved.resolved) == 2


def test_method_changes_are_not_presented_as_clean_source_changes(tmp_path: Path) -> None:
    before = _report(tmp_path, _source())
    after = _report(tmp_path, _source(), Config(max_steps=99_999))

    comparison = compare_reports(before, after)

    assert comparison.status is Comparability.PARTIALLY_COMPARABLE
    assert "configuration changed" in comparison.reasons


def test_comparison_distinguishes_incomplete_and_incomparable_reports(tmp_path: Path) -> None:
    complete = _report(tmp_path, _source())
    incomplete = deepcopy(complete)
    incomplete["analysis_state"] = "incomplete"
    incomplete["issues"] = [{"code": "DT1001", "path": "main.py", "message": "changed"}]

    degraded = compare_reports(complete, incomplete)

    assert degraded.status is Comparability.PARTIALLY_COMPARABLE
    assert "one or both analyses are incomplete" in degraded.reasons
    assert "input issues changed" in degraded.reasons

    other_world = deepcopy(complete)
    other_world["worlds"][0]["id"] = {"profile": "staging", "scenario": "worker"}
    incomparable = compare_reports(complete, other_world)

    assert incomparable.status is Comparability.INCOMPARABLE
    assert "reports have no common execution world" in incomparable.reasons


def test_source_membership_changes_are_visible_but_remain_source_changes(tmp_path: Path) -> None:
    before = _report(tmp_path, _source())
    after = deepcopy(before)
    after["source_universe"]["files"].append("new_module.py")

    comparison = compare_reports(before, after)
    payload = comparison.to_dict()

    assert comparison.status is Comparability.COMPARABLE
    assert comparison.added_source_files == ("new_module.py",)
    assert payload["summary"]["added_source_files"] == 1


def test_new_roots_and_worlds_are_source_changes(tmp_path: Path) -> None:
    before = _report(tmp_path, _source())
    after = _report(
        tmp_path,
        _source('@app.get("/health")\ndef health() -> None:\n    pass\n'),
    )
    (tmp_path / "test_main.py").write_text(
        "from main import live\n\ndef test_live() -> None:\n    live()\n", encoding="utf-8"
    )
    with_tests = semantic_report_dict(analyze(tmp_path, Config()))

    comparison = compare_reports(before, after)
    assert comparison.status is Comparability.COMPARABLE
    assert comparison.added_roots == ("production:web: main.health",)
    assert len(comparison.unchanged) == 1
    assert "roots added: 1" in render_comparison_text(comparison)

    grown = compare_reports(after, with_tests)
    assert grown.status is Comparability.COMPARABLE
    assert grown.added_worlds == ("tests:pytest",)
    assert grown.to_dict()["summary"]["added_worlds"] == 1
    assert [item["fingerprint"] for item in grown.unchanged] == [
        item["fingerprint"] for item in after["findings"]
    ]


def test_dependency_versions_matter_only_where_they_weaken_the_model(tmp_path: Path) -> None:
    before = _report(tmp_path, _source())
    bumped = deepcopy(before)
    bumped["descriptor"]["target_environment_digest"] = "other"
    bumped["target_environment"]["packages"] = [
        {"name": "httpx", "version": "0.28.1", "source": "uv.lock"}
    ]
    bumped["target_environment"]["issues"] = [
        {"code": "DT4002", "package": "fastapi", "version": "0.120.0", "message": "untested"}
    ]
    assert compare_reports(before, bumped).status is Comparability.COMPARABLE

    unsupported = deepcopy(bumped)
    unsupported["target_environment"]["issues"] = [
        {"code": "DT4001", "package": "fastapi", "version": "1.0.0", "message": "unsupported"}
    ]
    comparison = compare_reports(before, unsupported)
    assert comparison.status is Comparability.PARTIALLY_COMPARABLE
    assert comparison.reasons == ("support of target dependency versions changed",)


def test_analyzer_version_alone_keeps_reports_comparable(tmp_path: Path) -> None:
    before = _report(tmp_path, _source())
    after = deepcopy(before)
    after["tool"]["version"] = "99.0.0"

    assert compare_reports(before, after).status is Comparability.COMPARABLE
    assert apply_baseline(after, create_baseline(before, "reviewed")).comparable


def test_changed_group_is_correlated_but_not_silently_suppressed(tmp_path: Path) -> None:
    before = _report(
        tmp_path,
        _source("class Legacy:\n    def first(self) -> None:\n        pass\n"),
    )
    after = _report(
        tmp_path,
        _source(
            "class Legacy:\n"
            "    def first(self) -> None:\n"
            "        pass\n"
            "    def second(self) -> None:\n"
            "        pass\n"
        ),
    )

    comparison = compare_reports(before, after)

    assert comparison.changed
    assert comparison.added
    assert comparison.resolved


def test_semantic_report_validation_rejects_wrong_artifacts() -> None:
    with pytest.raises(ArtifactError, match="schema_version"):
        validate_semantic_report({})
    with pytest.raises(ArtifactError, match="not a Deadtrace"):
        validate_semantic_report({"schema_version": 1, "tool": {"name": "other"}})


def test_baseline_accepts_only_exact_findings_under_same_method(tmp_path: Path) -> None:
    original = _report(tmp_path, _source())
    baseline = create_baseline(original, "reviewed legacy debt")

    same = apply_baseline(original, baseline)
    assert same.comparable
    assert same.accepted == 1
    assert same.new == 0
    assert same.payload["findings"][0]["baseline_status"] == "accepted"

    changed = _report(tmp_path, _source("def new_candidate() -> None:\n    pass\n"))
    application = apply_baseline(changed, baseline)
    assert application.accepted == 1
    assert application.new == 1
    assert application.stale == 0

    incompatible = _report(tmp_path, _source(), Config(max_steps=99_999))
    rejected = apply_baseline(incompatible, baseline)
    assert not rejected.comparable
    assert rejected.reasons == ("configuration changed",)
    assert rejected.payload["baseline"]["reasons"] == ["configuration changed"]
    assert rejected.accepted == 0
    assert rejected.new == 1


def test_baseline_survives_new_tests_and_routes(tmp_path: Path) -> None:
    baseline = create_baseline(_report(tmp_path, _source()), "reviewed legacy debt")
    grown = _report(
        tmp_path,
        _source('@app.get("/health")\ndef health() -> None:\n    pass\n'),
    )
    (tmp_path / "test_main.py").write_text(
        "from main import live\n\ndef test_live() -> None:\n    live()\n", encoding="utf-8"
    )
    with_tests = semantic_report_dict(analyze(tmp_path, Config()))

    for report in (grown, with_tests):
        application = apply_baseline(report, baseline)
        assert application.comparable
        assert (application.accepted, application.new) == (1, 0)


def test_baseline_with_input_issues_is_comparable_with_itself(tmp_path: Path) -> None:
    (tmp_path / "broken.py").write_text("def broken(:\n", encoding="utf-8")
    report = _report(tmp_path, _source())
    assert report["issues"]
    baseline = json.loads(render_json_artifact(create_baseline(report, "reviewed")))

    assert apply_baseline(report, baseline).comparable


def test_baseline_update_carries_entries_whose_fingerprint_was_renewed(tmp_path: Path) -> None:
    report = _report(tmp_path, _source())
    baseline = create_baseline(deepcopy(report), "reviewed debt")
    baseline["entries"][0]["fingerprint"] = "rch001-0000000000000000"
    baseline["entries"][0]["members"][0]["line"] = 1

    refreshed = update_baseline(baseline, report)

    assert refreshed["entries"] == [
        {
            "fingerprint": report["findings"][0]["fingerprint"],
            "code": "RCH001",
            "members": report["findings"][0]["members"],
            "reason": "reviewed debt",
        }
    ]


def test_baseline_validation_and_json_are_deterministic(tmp_path: Path) -> None:
    baseline = create_baseline(_report(tmp_path, _source()), "reviewed")
    validate_baseline(baseline)
    assert render_json_artifact(baseline) == render_json_artifact(baseline)

    duplicate = dict(baseline)
    duplicate["entries"] = [*baseline["entries"], *baseline["entries"]]
    with pytest.raises(ArtifactError, match="duplicate baseline"):
        validate_baseline(duplicate)

    with pytest.raises(ArtifactError, match="reason"):
        create_baseline(_report(tmp_path, _source()), "  ")


def test_baseline_update_does_not_accept_new_findings_by_default(tmp_path: Path) -> None:
    original = _report(tmp_path, _source())
    baseline = create_baseline(original, "reviewed debt")
    changed = _report(tmp_path, _source("def new_candidate() -> None:\n    pass\n"))

    refreshed = update_baseline(baseline, changed)
    application = apply_baseline(changed, refreshed)

    assert application.comparable
    assert application.accepted == 1
    assert application.new == 1
    assert [entry["reason"] for entry in refreshed["entries"]] == ["reviewed debt"]

    accepted = update_baseline(
        baseline,
        changed,
        accept_new=True,
        reason="reviewed new debt",
    )
    accepted_application = apply_baseline(changed, accepted)
    assert accepted_application.accepted == 2
    assert accepted_application.new == 0
    assert {entry["reason"] for entry in accepted["entries"]} == {
        "reviewed debt",
        "reviewed new debt",
    }

    with pytest.raises(ArtifactError, match="non-empty reason"):
        update_baseline(baseline, changed, accept_new=True)


def test_capabilities_and_removed_worlds_follow_the_method_and_the_source(
    tmp_path: Path,
) -> None:
    without_tests = _report(
        tmp_path, _source('@app.get("/health")\ndef health() -> None:\n    pass\n')
    )
    assert "pytest.fixtures" in {item["id"] for item in without_tests["capabilities"]}
    (tmp_path / "test_main.py").write_text(
        "from main import live\n\ndef test_live() -> None:\n    live()\n", encoding="utf-8"
    )
    with_tests = semantic_report_dict(analyze(tmp_path, Config()))
    (tmp_path / "test_main.py").unlink()
    shrunk = _report(tmp_path, _source())

    assert without_tests["capabilities"] == with_tests["capabilities"]
    comparison = compare_reports(with_tests, shrunk)
    assert comparison.status is Comparability.COMPARABLE
    assert comparison.removed_worlds == ("tests:pytest",)
    assert comparison.removed_roots == ("production:web: main.health",)


def test_reports_are_read_up_to_the_report_limit_not_the_input_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = tmp_path / "report.json"
    report.write_text(render_json_artifact(_report(tmp_path, _source())), encoding="utf-8")
    monkeypatch.setattr("deadtrace.artifacts.MAX_ARTIFACT_BYTES", 10)

    assert read_json_artifact(report)["schema_version"] == 1
    monkeypatch.setattr("deadtrace.artifacts.MAX_REPORT_BYTES", 10)
    with pytest.raises(ArtifactError, match="limit is 10 bytes"):
        read_json_artifact(report)
