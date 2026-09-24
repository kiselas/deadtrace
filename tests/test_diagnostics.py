from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from deadtrace.analysis import analyze
from deadtrace.cli import app
from deadtrace.config import Config
from deadtrace.diagnostics import render_troubleshooting_json, troubleshooting_bundle


def test_troubleshooting_bundle_is_aggregated_and_omits_project_details(tmp_path: Path) -> None:
    secret = "VERY_PRIVATE_SOURCE_MARKER"
    (tmp_path / "private_name.py").write_text(
        f"""
from fastapi import FastAPI
app = FastAPI()

def candidate() -> str:
    return "{secret}"
""",
        encoding="utf-8",
    )
    result = analyze(tmp_path, Config())

    payload = troubleshooting_bundle(result)
    rendered = render_troubleshooting_json(result)

    assert payload["kind"] == "deadtrace-troubleshooting-bundle"
    assert payload["findings"]["counts"] == {"RCH001": 1}
    assert payload["inputs"]["files"] == 1
    assert secret not in rendered
    assert "private_name.py" not in rendered
    assert str(tmp_path) not in rendered
    assert "candidate" not in rendered
    assert "source text" in payload["privacy"]["omitted"]


def test_support_bundle_cli_previews_before_writing(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\n", encoding="utf-8"
    )
    output = tmp_path / "support.json"

    result = CliRunner().invoke(
        app,
        ["support-bundle", str(tmp_path), "--output", str(output)],
    )

    assert result.exit_code == 0
    assert "troubleshooting bundle preview" in result.stderr
    assert "omits source" in result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["kind"] == "deadtrace-troubleshooting-bundle"
