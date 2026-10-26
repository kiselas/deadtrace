from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from deadtrace.analysis import AnalysisResult, analyze
from deadtrace.baseline import apply_baseline, create_baseline, update_baseline
from deadtrace.cli import app
from deadtrace.comparison import compare_reports, render_comparison_text
from deadtrace.config import Config, KeepConfig
from deadtrace.resolution import explain_resolved
from deadtrace.semantic_report import semantic_report_dict

runner = CliRunner()

MAIN = """
from fastapi import FastAPI
import plugins

app = FastAPI()
NAME = input()

@app.get("/")
def live() -> None:
    pass
"""

PLUGINS = """
def first_candidate() -> None:
    pass

def second_candidate() -> None:
    pass
"""


def _scan(
    root: Path, main: str = MAIN, plugins: str = PLUGINS, config: Config | None = None
) -> AnalysisResult:
    (root / "main.py").write_text(main, encoding="utf-8")
    (root / "plugins.py").write_text(plugins, encoding="utf-8")
    return analyze(root, config or Config())


def _annotated(before: dict[str, Any], result: AnalysisResult) -> dict[str, Any]:
    """The later report as ``scan --baseline`` writes it, with a baseline of the earlier one."""

    return apply_baseline(
        semantic_report_dict(result),
        create_baseline(before, "reviewed"),
        explain_stale=lambda entries: explain_resolved(result, entries),
    ).payload


def _by_title(comparison_resolved: tuple[dict[str, Any], ...]) -> dict[str, dict[str, Any]]:
    return {item["title"].rpartition(" ")[2]: item["resolution"] for item in comparison_resolved}


def test_new_dynamic_dispatch_protects_without_a_consumer(tmp_path: Path) -> None:
    before = semantic_report_dict(_scan(tmp_path))
    after = _annotated(
        before, _scan(tmp_path, MAIN.replace("    pass", "    getattr(plugins, NAME)()"))
    )

    comparison = compare_reports(before, after)
    resolutions = _by_title(comparison.resolved)

    assert set(resolutions) == {"first_candidate", "second_candidate"}
    member = resolutions["first_candidate"]["members"][0]
    assert resolutions["first_candidate"]["cause"] == "protected"
    assert member["evidence"]["boundary"]["path"] == "main.py"
    assert member["evidence"]["boundary"]["name"] == "main.live"
    assert member["evidence"]["sole"] is True
    assert member["evidence"]["new_boundary"] is True
    assert comparison.to_dict()["summary"]["resolved_by_cause"] == {"protected": 2}
    text = render_comparison_text(comparison)
    assert "Resolved by cause: protected 2" in text
    assert "no resolved path reaches it" in text


def test_a_caller_that_may_run_only_through_a_boundary_is_named(tmp_path: Path) -> None:
    before = semantic_report_dict(_scan(tmp_path))
    main = MAIN.replace("import plugins", "import threading\nimport plugins").replace(
        "    pass", "    threading.Thread(target=plugins.worker).start()"
    )
    plugins = PLUGINS + "\ndef worker() -> None:\n    first_candidate()\n"
    after = _annotated(before, _scan(tmp_path, main, plugins))

    comparison = compare_reports(before, after)
    resolution = _by_title(comparison.resolved)["first_candidate"]

    evidence = resolution["members"][0]["evidence"]
    assert resolution["cause"] == "protected"
    assert evidence["edge"] == "call"
    assert evidence["from"]["name"] == "plugins.worker"
    assert evidence["boundary"]["name"] == "main.live"
    assert "call from plugins.worker (plugins.py:" in render_comparison_text(comparison)


def test_counterfactuals_stop_after_one_more_solve_of_every_world(tmp_path: Path) -> None:
    before = semantic_report_dict(_scan(tmp_path))
    main = MAIN.replace("import plugins", "import threading\nimport plugins").replace(
        "    pass", "    threading.Thread(target=plugins.first_candidate).start()"
    ) + (
        '\n@app.get("/other")\ndef other() -> None:\n'
        "    threading.Thread(target=plugins.second_candidate).start()\n"
    )
    result = _scan(tmp_path, main)
    after = _annotated(before, result)

    sole = {
        item["members"][0]["qualified_name"]: item["members"][0]["evidence"]["sole"]
        for item in after["baseline"]["stale_entries"]
    }

    # Each candidate has its own boundary, and the only world is solved once more for the first.
    assert [world.id.key for world in result.snapshot.worlds] == ["production:web"]
    assert sole == {"first_candidate": True, "second_candidate": None}


def test_a_second_boundary_makes_neither_sole(tmp_path: Path) -> None:
    before = semantic_report_dict(_scan(tmp_path))
    main = MAIN.replace("    pass", "    getattr(plugins, NAME)()") + (
        '\n@app.get("/other")\ndef other() -> None:\n    getattr(plugins, NAME)()\n'
    )
    after = _annotated(before, _scan(tmp_path, main))

    resolution = _by_title(compare_reports(before, after).resolved)["first_candidate"]

    assert resolution["cause"] == "protected"
    assert resolution["members"][0]["evidence"]["sole"] is False


def test_a_resolved_call_names_the_consumer(tmp_path: Path) -> None:
    before = semantic_report_dict(_scan(tmp_path))
    after = _annotated(before, _scan(tmp_path, MAIN.replace("pass", "plugins.first_candidate()")))

    comparison = compare_reports(before, after)
    resolution = _by_title(comparison.resolved)["first_candidate"]

    assert resolution["cause"] == "reached"
    assert resolution["members"][0]["evidence"] == {
        "world": "production:web",
        "edge": "call",
        "from": {"name": "main.live", "path": "main.py", "line": 9},
    }
    assert [item["title"] for item in comparison.unchanged] == [
        "Unreached component: second_candidate"
    ]


def test_deleted_code_and_a_regrouped_component(tmp_path: Path) -> None:
    plugins = PLUGINS.replace("def second_candidate() -> None:\n    pass", "") + (
        "\ndef caller() -> None:\n    callee()\n\ndef callee() -> None:\n    pass\n"
    )
    before = semantic_report_dict(_scan(tmp_path, plugins=plugins))
    after_plugins = plugins.replace("def first_candidate() -> None:\n    pass\n", "").replace(
        "def caller() -> None:\n    callee()\n", ""
    )
    after = _annotated(before, _scan(tmp_path, plugins=after_plugins))

    resolutions = _by_title(compare_reports(before, after).resolved)

    assert resolutions["first_candidate"]["cause"] == "deleted"
    regrouped = resolutions["caller"]
    assert regrouped["cause"] == "regrouped"
    statuses = {item["qualified_name"]: item["status"] for item in regrouped["members"]}
    assert statuses == {"caller": "deleted", "callee": "regrouped"}


def test_a_keep_contract_is_kept_and_the_method_change_stays_visible(tmp_path: Path) -> None:
    before = semantic_report_dict(_scan(tmp_path))
    keep = KeepConfig(
        target="plugins:first_candidate", reason="loaded by name", profiles=("production",)
    )
    after = _annotated(before, _scan(tmp_path, config=Config(keep=(keep,))))

    comparison = compare_reports(before, after)

    assert comparison.reasons == ("configuration changed",)
    assert _by_title(comparison.resolved)["first_candidate"]["cause"] == "kept"


def test_a_blocked_finding_is_not_read_as_resolved(tmp_path: Path) -> None:
    before = semantic_report_dict(_scan(tmp_path))
    (tmp_path / "settings.yaml").write_text("handler: first_candidate\n", encoding="utf-8")
    result = _scan(tmp_path)
    plain = semantic_report_dict(result)

    from_reports = _by_title(compare_reports(before, plain).resolved)
    from_scan = _by_title(compare_reports(before, _annotated(before, result)).resolved)

    assert from_reports["first_candidate"] == {
        "cause": "blocked",
        "blocked": ["mentioned_in_config"],
    }
    assert from_scan["first_candidate"] == from_reports["first_candidate"]


def test_reports_alone_leave_a_protected_finding_unattributed(tmp_path: Path) -> None:
    before = semantic_report_dict(_scan(tmp_path))
    after = semantic_report_dict(
        _scan(tmp_path, MAIN.replace("    pass", "    getattr(plugins, NAME)()"))
    )

    comparison = compare_reports(before, after)

    assert {item["resolution"]["cause"] for item in comparison.resolved} == {"unattributed"}
    assert "scan with --baseline" in render_comparison_text(comparison)


def test_novelty_of_a_boundary_follows_the_guards_of_the_earlier_report(tmp_path: Path) -> None:
    before = semantic_report_dict(_scan(tmp_path))
    after = _annotated(
        before, _scan(tmp_path, MAIN.replace("    pass", "    getattr(plugins, NAME)()"))
    )
    message = "dynamic getattr call target cannot be resolved statically"

    def novelty(origin: str | None) -> object:
        # The earlier report already lists the guard: grouped by message, or with its origin.
        earlier = deepcopy(before)
        guard = {"code": "DT2002", "message": message, "origin": origin}
        earlier["worlds"][0]["limitations"].append(guard if origin else {**guard, "origins": 1})
        resolution = _by_title(compare_reports(earlier, after).resolved)["first_candidate"]
        return resolution["members"][0]["evidence"]["new_boundary"]

    assert novelty(None) is None
    assert novelty("main.live") is False
    assert novelty("main.elsewhere") is True


def test_scan_with_baseline_prints_stale_causes(tmp_path: Path) -> None:
    _scan(tmp_path)
    before = tmp_path / "before.json"
    baseline = tmp_path / "baseline.json"
    runner.invoke(app, ["scan", str(tmp_path), "--format", "json", "--output", str(before)])
    runner.invoke(
        app,
        ["baseline", "create", str(before), "--output", str(baseline), "--reason", "reviewed"],
    )
    _scan(tmp_path, MAIN.replace("    pass", "    getattr(plugins, NAME)()"))

    result = runner.invoke(app, ["scan", str(tmp_path), "--baseline", str(baseline)])

    assert result.exit_code == 0
    assert "stale=2" in result.stdout
    assert "Stale by cause: protected 2" in result.stdout
    assert "the finding returns without it" in result.stdout


def _scan_saved(root: Path, name: str, *extra: str) -> Any:
    target = root / name
    result = runner.invoke(
        app, ["scan", str(root), "--format", "json", "--output", str(target), *extra]
    )
    assert result.exit_code == 0, result.output
    return json.loads(target.read_text(encoding="utf-8"))


def test_scan_with_a_previous_report_needs_no_baseline(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    _scan(source)
    _scan_saved(source, "before.json")
    _scan(source, MAIN.replace("    pass", "    getattr(plugins, NAME)()"))
    before = source / "before.json"

    text = runner.invoke(app, ["scan", str(source), "--previous", str(before)])
    after = _scan_saved(source, "after.json", "--previous", str(before))
    comparison = compare_reports(json.loads(before.read_text(encoding="utf-8")), after)

    assert text.exit_code == 0
    assert "Previous report: comparable | new=0 | resolved=2" in text.stdout
    assert "Resolved by cause: protected 2" in text.stdout
    assert after["previous"]["resolved_by_cause"] == {"protected": 2}
    assert "baseline" not in after
    assert {item["resolution"]["cause"] for item in comparison.resolved} == {"protected"}


def test_previous_and_baseline_annotate_one_report(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    _scan(source)
    _scan_saved(source, "before.json")
    before = source / "before.json"
    baseline = tmp_path / "baseline.json"
    runner.invoke(
        app,
        ["baseline", "create", str(before), "--output", str(baseline), "--reason", "reviewed"],
    )
    _scan(source, MAIN.replace("pass", "plugins.first_candidate()"))

    after = _scan_saved(
        source, "after.json", "--baseline", str(baseline), "--previous", str(before)
    )

    assert after["summary"]["stale_baseline_count"] == 1
    assert after["previous"]["resolved"] == after["baseline"]["stale_entries"]
    assert after["previous"]["resolved"][0]["cause"] == "reached"


def test_an_unreadable_previous_report_is_an_operational_error(tmp_path: Path) -> None:
    _scan(tmp_path)
    broken = tmp_path / "previous.json"
    broken.write_text('{"schema_version": 1}', encoding="utf-8")

    result = runner.invoke(app, ["scan", str(tmp_path), "--previous", str(broken)])

    assert result.exit_code == 2
    assert "previous report error" in result.output


def test_reach_from_tests_hides_an_unreached_component(tmp_path: Path) -> None:
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "helpers.py").write_text("def helper() -> None:\n    pass\n", encoding="utf-8")
    before = semantic_report_dict(_scan(tmp_path))
    (tests / "test_loading.py").write_text(
        "import plugins\nfrom tests import helpers\n\n"
        "def test_helper() -> None:\n    helpers.helper()\n\n"
        "def test_any(name: str = input()) -> None:\n    getattr(plugins, name)()\n",
        encoding="utf-8",
    )
    after = _annotated(before, _scan(tmp_path))

    resolutions = _by_title(compare_reports(before, after).resolved)

    # Test code that a test now calls is not reported; production code is only possibly running.
    helper = resolutions["helper"]["members"][0]
    candidate = resolutions["first_candidate"]["members"][0]
    assert helper["status"] == "reached"
    assert helper["evidence"]["world"] == "tests:pytest"
    assert helper["evidence"]["from"]["name"] == "tests.test_loading.test_helper"
    assert candidate["status"] == "protected"
    assert candidate["evidence"]["world"] == "tests:pytest"
    assert candidate["evidence"]["boundary"]["name"] == "tests.test_loading.test_any"
    assert candidate["evidence"]["sole"] is True


def _baseline_cli(*args: str) -> Any:
    result = runner.invoke(app, ["baseline", *args])
    assert result.exit_code == 0, result.output
    return result


def test_protected_entries_stay_dormant_until_the_boundary_goes(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    _scan(source)
    _scan_saved(source, "before.json")
    first = tmp_path / "first.json"
    _baseline_cli(
        "create", str(source / "before.json"), "--output", str(first), "--reason", "reviewed"
    )
    _scan(source, MAIN.replace("    pass", "    getattr(plugins, NAME)()"))
    _scan_saved(source, "annotated.json", "--baseline", str(first))
    _scan_saved(source, "plain.json")
    kept, dropped = tmp_path / "kept.json", tmp_path / "dropped.json"

    with_causes = _baseline_cli(
        "update", str(first), str(source / "annotated.json"), "--output", str(kept)
    )
    without_causes = _baseline_cli(
        "update", str(first), str(source / "plain.json"), "--output", str(dropped)
    )
    hidden = runner.invoke(app, ["scan", str(source), "--baseline", str(kept)])
    _scan(source)
    returned = runner.invoke(app, ["scan", str(source), "--baseline", str(kept), "--fail-on-new"])
    lost = runner.invoke(app, ["scan", str(source), "--baseline", str(dropped), "--fail-on-new"])

    entries = json.loads(kept.read_text(encoding="utf-8"))["entries"]
    assert [entry["dormant"]["cause"] for entry in entries] == ["protected", "protected"]
    assert entries[0]["dormant"]["boundaries"][0]["name"] == "main.live"
    assert "kept 2 dormant entries" in with_causes.output
    assert json.loads(dropped.read_text(encoding="utf-8"))["entries"] == []
    assert "dropped 2 stale entries without a recorded cause" in without_causes.output
    assert "stale=2 | dormant=2" in hidden.stdout
    # The boundary is gone: the dormant entries accept the findings again; dropped ones do not.
    assert returned.exit_code == 0
    assert "accepted=2 | new=0" in returned.stdout
    assert lost.exit_code == 1


def test_a_returned_finding_is_no_longer_dormant_and_deleted_code_is_dropped(
    tmp_path: Path,
) -> None:
    before = semantic_report_dict(_scan(tmp_path))
    baseline = create_baseline(before, "reviewed")
    protected = _annotated(
        before, _scan(tmp_path, MAIN.replace("    pass", "    getattr(plugins, NAME)()"))
    )
    dormant = update_baseline(baseline, protected)
    # The boundary goes and one candidate is deleted while the baseline holds both as dormant.
    result = _scan(
        tmp_path, plugins=PLUGINS.replace("def second_candidate() -> None:\n    pass\n", "")
    )
    returned = apply_baseline(
        semantic_report_dict(result),
        dormant,
        explain_stale=lambda entries: explain_resolved(result, entries),
    ).payload

    refreshed = update_baseline(dormant, returned)

    assert [entry["qualified_name"] for entry in refreshed["entries"][0]["members"]] == [
        "first_candidate"
    ]
    assert len(refreshed["entries"]) == 1
    assert "dormant" not in refreshed["entries"][0]
    assert returned["baseline"]["stale_entries"][0]["cause"] == "deleted"
