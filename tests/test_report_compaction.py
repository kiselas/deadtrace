"""The JSON report lists world members only on request and guards by message (ADR-0079)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from deadtrace.cli import app
from deadtrace.comparison import compare_reports

runner = CliRunner()


def _project(root: Path) -> Path:
    (root / "_tool.py").write_text(
        "import importlib\n\n\ndef load(name):\n    return importlib.import_module(name).run\n\n\n"
        "def main() -> None:\n    print(load('x'))\n\n\n"
        "if __name__ == '__main__':\n    main()\n",
        encoding="utf-8",
    )
    (root / "_other.py").write_text(
        "def run() -> None:\n    pass\n\n\nif __name__ == '__main__':\n    run()\n",
        encoding="utf-8",
    )
    (root / "tests").mkdir()
    (root / "tests" / "test_tool.py").write_text(
        "from _other import run\n\n\ndef test_run():\n    run()\n", encoding="utf-8"
    )
    return root


def _scan(root: Path, *extra: str) -> dict[str, Any]:
    result = runner.invoke(app, ["scan", str(root), "--format", "json", *extra])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict)
    return payload


def test_default_report_counts_world_members(tmp_path: Path) -> None:
    payload = _scan(_project(tmp_path))

    worlds = payload["worlds"]
    assert isinstance(worlds, list) and worlds
    for world in worlds:
        assert "resolved_may_run" not in world
        assert isinstance(world["resolved_count"], int)
        assert isinstance(world["conservative_count"], int)
    assert isinstance(payload["shared_limitations"], list)


def test_world_members_option_lists_them(tmp_path: Path) -> None:
    payload = _scan(_project(tmp_path), "--world-members")

    worlds = payload["worlds"]
    assert isinstance(worlds, list)
    assert all(len(world["resolved_may_run"]) == world["resolved_count"] for world in worlds)


def test_guards_are_grouped_by_message_by_default(tmp_path: Path) -> None:
    payload = _scan(_project(tmp_path))
    guards = [
        item
        for world in payload["worlds"]
        for item in world["limitations"]
        if item["code"] == "DT2002"
    ] + [item for item in payload["shared_limitations"] if item["code"] == "DT2002"]

    assert guards
    assert all(item["origin"] is None and item["origins"] >= 1 for item in guards)


def test_compact_and_full_reports_compare_alike(tmp_path: Path) -> None:
    root = _project(tmp_path)
    full = _scan(root, "--world-members")
    compact = _scan(root)

    comparison = compare_reports(full, compact)

    assert not comparison.added and not comparison.resolved
    assert not comparison.new_limitations and not comparison.resolved_limitations
