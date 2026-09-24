from __future__ import annotations

import json
import math
import os
from pathlib import Path

import pytest

from deadtrace.benchmark import (
    PARSER,
    TOP_LEVEL_STAGES,
    VOLATILE_FIELDS,
    benchmark,
    render_benchmark_json,
    render_benchmark_text,
)
from deadtrace.config import Config
from deadtrace.timing import COUNTERS, STAGES

MAIN_SOURCE = (
    "from fastapi import FastAPI\n\napp = FastAPI()\n\n\n"
    "@app.get('/')\ndef live() -> str:\n    return 'live'\n"
)
HELPER_SOURCE = "def helper() -> int:\n    return 1\n"


def _write_project(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "main.py").write_text(MAIN_SOURCE, encoding="utf-8", newline="\n")
    (root / "helper.py").write_text(HELPER_SOURCE, encoding="utf-8", newline="\n")
    return root


def test_benchmark_reports_stages_and_stable_descriptor(tmp_path: Path) -> None:
    result = benchmark(_write_project(tmp_path), Config(), 2)
    payload = json.loads(render_benchmark_json(result))

    assert result.runs == 2
    assert len(result.samples) == 2
    assert payload["kind"] == "deadtrace-benchmark"
    assert payload["schema_version"] == 4
    assert set(payload["summary"]) == {*TOP_LEVEL_STAGES, "stages"}
    assert set(payload["summary"]["stages"]) == set(STAGES)
    for sample in payload["samples"]:
        assert set(sample) == {*TOP_LEVEL_STAGES, "stages"}
        assert set(sample["stages"]) == set(STAGES)
    assert payload["summary"]["total_seconds"]["max"] >= 0
    assert payload["descriptor"]["model_revision"] == result.model_revision
    assert payload["descriptor"]["parser"] == PARSER
    assert payload["host"]["python_version"]
    assert result.process_peak_rss_bytes is None or result.process_peak_rss_bytes > 0
    assert "without tracemalloc" in payload["notes"]["memory"]
    assert payload["volatile_fields"] == list(VOLATILE_FIELDS)


def test_sub_stage_totals_are_internally_consistent(tmp_path: Path) -> None:
    result = benchmark(_write_project(tmp_path), Config(), 3)

    for sample in result.samples:
        stages = sample["stages"]
        for parent in ("collect", "frontend", "solve"):
            nested = sum(value for name, value in stages.items() if name.startswith(f"{parent}."))
            assert 0.0 <= nested <= sample[f"{parent}_seconds"] + 1e-9, parent
        assert stages["report.render"] == sample["report_seconds"]
        assert math.isclose(
            sample["collect_seconds"] + sample["frontend_seconds"] + sample["solve_seconds"],
            sample["total_seconds"],
            rel_tol=1e-9,
            abs_tol=1e-9,
        )


def test_counters_are_deterministic_and_describe_the_input(tmp_path: Path) -> None:
    result = benchmark(_write_project(tmp_path), Config(), 2)
    counters = result.counters

    assert set(counters) == {"files", "lines", "nodes", "edges", "worlds", *COUNTERS}
    assert counters["files"] == 2
    assert counters["lines"] == MAIN_SOURCE.count("\n") + 1 + HELPER_SOURCE.count("\n") + 1
    assert counters["collect.attempts"] == 1
    assert counters["collect.files_read"] == 2
    assert counters["collect.characters"] == len(MAIN_SOURCE) + len(HELPER_SOURCE)
    assert counters["collect.read_errors"] == 0
    assert counters["frontend.modules"] == 2
    assert counters["frontend.parse_failures"] == 0
    assert counters["frontend.symbols"] == 2
    assert counters["frontend.import_bindings"] == 1
    assert counters["worlds"] == 1
    assert counters["findings"] == 1


def test_artifact_is_deterministic_outside_documented_volatile_fields(tmp_path: Path) -> None:
    root = _write_project(tmp_path)

    first = json.loads(render_benchmark_json(benchmark(root, Config(), 1)))
    second = json.loads(render_benchmark_json(benchmark(root, Config(), 1)))
    for field in VOLATILE_FIELDS:
        first.pop(field)
        second.pop(field)

    assert first == second


def test_artifact_contains_no_paths_or_user_names(tmp_path: Path) -> None:
    root = _write_project(tmp_path / "private-project-marker")
    rendered = render_benchmark_json(benchmark(root, Config(), 1))

    assert "private-project-marker" not in rendered
    assert str(tmp_path) not in rendered
    assert "helper" not in rendered
    assert "live" not in rendered
    for variable in ("USERNAME", "USER"):
        user = os.environ.get(variable, "")
        if len(user) > 2:
            assert user not in rendered


def test_text_rendering_lists_host_tool_sub_stages_and_counters(tmp_path: Path) -> None:
    rendered = render_benchmark_text(benchmark(_write_project(tmp_path), Config(), 1))

    assert rendered.startswith("Deadtrace benchmark (1 runs)\n")
    assert "Host: " in rendered
    assert "Tool: deadtrace " in rendered
    assert "Process peak RSS:" in rendered
    assert "report_seconds: min=" in rendered
    assert "Sub-stages (median seconds):\n  collect.discover: " in rendered
    assert "Counters:\n  collect.attempts: 1\n" in rendered


@pytest.mark.parametrize("runs", [0, 101])
def test_benchmark_rejects_unbounded_run_counts(tmp_path: Path, runs: int) -> None:
    with pytest.raises(ValueError, match="between 1 and 100"):
        benchmark(tmp_path, Config(), runs)
