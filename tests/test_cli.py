from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from deadtrace.cli import app

runner = CliRunner()


def test_help_and_version() -> None:
    help_result = runner.invoke(app, ["--help"])
    version_result = runner.invoke(app, ["--version"])

    assert help_result.exit_code == 0
    assert "framework-aware" in help_result.stdout
    assert "scan" in help_result.stdout
    assert version_result.exit_code == 0
    assert version_result.stdout.startswith("deadtrace ")


def test_json_stdout_is_not_mixed_with_diagnostics(tmp_path: Path) -> None:
    (tmp_path / "good.py").write_text("def good():\n    pass\n", encoding="utf-8")
    (tmp_path / "bad.py").write_text("def bad(:\n", encoding="utf-8")

    result = runner.invoke(app, ["scan", str(tmp_path), "--format", "json"])

    assert result.exit_code == 2
    payload = json.loads(result.stdout)
    assert len(payload["issues"]) == 1
    assert "DT1001" in result.stderr
    assert "DT1001" not in result.stdout.splitlines()[0]


def test_invalid_configuration_uses_exit_code_two(tmp_path: Path) -> None:
    (tmp_path / "target.py").write_text("def target():\n    pass\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        "[tool.deadtrace]\nnot-real = true\n", encoding="utf-8"
    )

    result = runner.invoke(app, ["scan", str(tmp_path), "--format", "json"])

    assert result.exit_code == 2
    assert result.stdout == ""
    assert "configuration error" in result.stderr


def test_cases_validate_command(project_root: Path) -> None:
    result = runner.invoke(app, ["cases", "validate", str(project_root / "fixtures" / "cases")])

    assert result.exit_code == 0, result.output
    assert "Validated 6 cases" in result.stdout


def test_cases_validate_reports_errors(tmp_path: Path) -> None:
    result = runner.invoke(app, ["cases", "validate", str(tmp_path)])

    assert result.exit_code == 1
    assert "case validation error" in result.stderr


def test_semantic_scan_finding_policy_and_saved_explanation(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text(
        """
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def endpoint() -> str:
    return "ok"

def candidate() -> None:
    pass
""",
        encoding="utf-8",
    )
    report_path = tmp_path / "report.json"

    result = runner.invoke(
        app,
        [
            "scan",
            str(tmp_path),
            "--format",
            "json",
            "--output",
            str(report_path),
            "--fail-on-findings",
        ],
    )

    assert result.exit_code == 1
    assert result.stdout == ""
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    finding = next(item for item in payload["findings"] if item["code"] == "RCH001")
    explanation = runner.invoke(
        app,
        ["explain", finding["fingerprint"], "--report", str(report_path)],
    )
    assert explanation.exit_code == 0
    assert finding["fingerprint"] in explanation.stdout


def test_doctor_reports_incomplete_rootless_project(tmp_path: Path) -> None:
    (tmp_path / "_module.py").write_text("def item():\n    pass\n", encoding="utf-8")

    result = runner.invoke(app, ["doctor", str(tmp_path)])

    assert result.exit_code == 0
    assert "production:application: invalid" in result.stdout
    assert "DT3004" in result.stdout


def test_inventory_only_and_require_complete_modes(tmp_path: Path) -> None:
    (tmp_path / "_module.py").write_text("def item():\n    pass\n", encoding="utf-8")

    inventory = runner.invoke(app, ["scan", str(tmp_path), "--format", "json", "--inventory-only"])
    required = runner.invoke(app, ["scan", str(tmp_path), "--require-complete"])

    assert inventory.exit_code == 0
    assert json.loads(inventory.stdout)["analysis_state"] == "inventory_only"
    assert required.exit_code == 2
    assert "incomplete" in required.stdout


def test_explain_and_output_failures_are_exit_two(tmp_path: Path) -> None:
    invalid_report = tmp_path / "invalid.json"
    invalid_report.write_text("not json", encoding="utf-8")
    missing_report = tmp_path / "missing.json"
    missing_report.write_text('{"findings": []}', encoding="utf-8")
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\n", encoding="utf-8"
    )

    invalid = runner.invoke(app, ["explain", "missing", "--report", str(invalid_report)])
    missing = runner.invoke(app, ["explain", "missing", "--report", str(missing_report)])
    output_error = runner.invoke(
        app,
        ["scan", str(source), "--format", "json", "--output", str(tmp_path)],
    )

    assert invalid.exit_code == 2
    assert "report error" in invalid.stderr
    assert missing.exit_code == 2
    assert "finding not present" in missing.stderr
    assert output_error.exit_code == 2
    assert "cannot write report" in output_error.stderr


def test_doctor_rejects_invalid_configuration(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[tool.deadtrace]\nunknown = true\n", encoding="utf-8")

    result = runner.invoke(app, ["doctor", str(tmp_path)])

    assert result.exit_code == 2
    assert "configuration error" in result.stderr


def test_baseline_and_comparison_ci_workflow(tmp_path: Path) -> None:
    source = tmp_path / "main.py"
    source.write_text(
        """
from fastapi import FastAPI
app = FastAPI()

@app.get("/")
def live() -> None:
    pass

def existing() -> None:
    pass
""",
        encoding="utf-8",
    )
    before = tmp_path / "before.json"
    baseline = tmp_path / "baseline.json"
    after = tmp_path / "after.json"

    first = runner.invoke(
        app,
        ["scan", str(tmp_path), "--format", "json", "--output", str(before)],
    )
    created = runner.invoke(
        app,
        [
            "baseline",
            "create",
            str(before),
            "--output",
            str(baseline),
            "--reason",
            "reviewed debt",
        ],
    )
    accepted = runner.invoke(
        app,
        [
            "scan",
            str(tmp_path),
            "--format",
            "json",
            "--baseline",
            str(baseline),
            "--fail-on-new",
        ],
    )

    assert first.exit_code == 0
    assert created.exit_code == 0
    assert accepted.exit_code == 0
    accepted_payload = json.loads(accepted.stdout)
    assert accepted_payload["summary"]["baselined_finding_count"] == 1
    assert accepted_payload["summary"]["new_finding_count"] == 0

    source.write_text(
        source.read_text(encoding="utf-8") + "\ndef new_candidate() -> None:\n    pass\n",
        encoding="utf-8",
    )
    new = runner.invoke(
        app,
        [
            "scan",
            str(tmp_path),
            "--format",
            "json",
            "--baseline",
            str(baseline),
            "--fail-on-new",
            "--output",
            str(after),
        ],
    )
    compared = runner.invoke(
        app,
        ["compare", str(before), str(after), "--format", "json", "--fail-on-new"],
    )

    assert new.exit_code == 1
    assert compared.exit_code == 1
    comparison = json.loads(compared.stdout)
    assert comparison["comparability"] == "comparable"
    assert comparison["summary"]["added_findings"] == 1

    refreshed = tmp_path / "baseline-refreshed.json"
    accepted_new = tmp_path / "baseline-with-new.json"
    update_without_accepting = runner.invoke(
        app,
        [
            "baseline",
            "update",
            str(baseline),
            str(after),
            "--output",
            str(refreshed),
        ],
    )
    still_new = runner.invoke(
        app,
        [
            "scan",
            str(tmp_path),
            "--format",
            "json",
            "--baseline",
            str(refreshed),
            "--fail-on-new",
        ],
    )
    update_accepting = runner.invoke(
        app,
        [
            "baseline",
            "update",
            str(baseline),
            str(after),
            "--output",
            str(accepted_new),
            "--accept-new",
            "--reason",
            "reviewed new debt",
        ],
    )
    no_longer_new = runner.invoke(
        app,
        [
            "scan",
            str(tmp_path),
            "--format",
            "json",
            "--baseline",
            str(accepted_new),
            "--fail-on-new",
        ],
    )

    assert update_without_accepting.exit_code == 0
    assert still_new.exit_code == 1
    assert update_accepting.exit_code == 0
    assert no_longer_new.exit_code == 0


def test_baseline_workflow_rejects_unsafe_or_ambiguous_inputs(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\n", encoding="utf-8"
    )
    missing_baseline = runner.invoke(app, ["scan", str(tmp_path), "--fail-on-new"])
    invalid = tmp_path / "invalid.json"
    invalid.write_text("{}", encoding="utf-8")
    invalid_baseline = runner.invoke(
        app,
        ["scan", str(tmp_path), "--baseline", str(invalid)],
    )
    existing = runner.invoke(
        app,
        [
            "baseline",
            "create",
            str(invalid),
            "--output",
            str(invalid),
            "--reason",
            "reviewed",
        ],
    )

    assert missing_baseline.exit_code == 2
    assert "requires --baseline" in missing_baseline.stderr
    assert invalid_baseline.exit_code == 2
    assert "baseline error" in invalid_baseline.stderr
    assert existing.exit_code == 2
    assert "already exists" in existing.stderr


def test_fail_on_new_requires_comparable_reports(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\n", encoding="utf-8"
    )
    before = tmp_path / "before.json"
    after = tmp_path / "after.json"
    assert (
        runner.invoke(
            app, ["scan", str(tmp_path), "--format", "json", "--output", str(before)]
        ).exit_code
        == 0
    )
    (tmp_path / "pyproject.toml").write_text(
        "[tool.deadtrace]\nmax-steps = 99999\n", encoding="utf-8"
    )
    assert (
        runner.invoke(
            app, ["scan", str(tmp_path), "--format", "json", "--output", str(after)]
        ).exit_code
        == 0
    )

    result = runner.invoke(app, ["compare", str(before), str(after), "--fail-on-new"])

    assert result.exit_code == 2
    assert "partially_comparable" in result.stdout
