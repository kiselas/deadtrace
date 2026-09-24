"""The performance budget check of ``benchmarks/check_budget.py`` (roadmap PERF-04)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


def _checker(project_root: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "check_budget", project_root / "benchmarks" / "check_budget.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _artifact(median: float, rss: int | None) -> dict[str, Any]:
    return {
        "kind": "deadtrace-benchmark",
        "schema_version": 4,
        "runs": 3,
        "counters": {"lines": 50_000},
        "summary": {"total_seconds": {"median": median, "min": median, "max": median}},
        "process_peak_rss_bytes": rss,
    }


def test_artifacts_within_the_budget_pass(project_root: Path, tmp_path: Path) -> None:
    checker = _checker(project_root)
    path = tmp_path / "scale.json"
    path.write_text(json.dumps(_artifact(1.5, 90 * 2**20)), encoding="utf-8")

    assert checker.main([str(path)]) == 0


@pytest.mark.parametrize(
    ("artifact", "problem"),
    [
        (_artifact(30.0, 90 * 2**20), "median total 30.00 s is not below 30 s"),
        (_artifact(1.0, 2**30), "peak RSS 1024 MiB is not below 1024 MiB"),
        (_artifact(1.0, None), "peak RSS was not reported"),
        ({"kind": "other"}, "not a schema-4 deadtrace benchmark artifact"),
    ],
)
def test_budget_violations_are_named(
    project_root: Path, artifact: dict[str, Any], problem: str
) -> None:
    checker = _checker(project_root)

    assert checker.check(artifact, max_seconds=30.0, max_rss_bytes=2**30) == [problem]


def test_any_failing_artifact_fails_the_run(project_root: Path, tmp_path: Path) -> None:
    checker = _checker(project_root)
    good = tmp_path / "good.json"
    slow = tmp_path / "slow.json"
    good.write_text(json.dumps(_artifact(1.0, 2**20)), encoding="utf-8")
    slow.write_text(json.dumps(_artifact(4.0, 2**20)), encoding="utf-8")

    assert checker.main([str(good), str(slow), "--max-seconds", "3"]) == 1
