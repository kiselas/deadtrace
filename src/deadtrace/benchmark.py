"""Repeatable in-process performance measurements for the static pipeline."""

from __future__ import annotations

import os
import platform
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from deadtrace import __version__
from deadtrace.analysis import AnalysisResult, analyze
from deadtrace.artifacts import render_json_artifact
from deadtrace.config import Config
from deadtrace.semantic_report import render_semantic_json
from deadtrace.timing import STAGES

TOP_LEVEL_STAGES = (
    "collect_seconds",
    "frontend_seconds",
    "solve_seconds",
    "report_seconds",
    "total_seconds",
)
"""Wall-clock stages of one sample. ``total_seconds`` covers the analysis only."""

VOLATILE_FIELDS = ("host", "samples", "summary", "process_peak_rss_bytes")
"""Artifact fields that may differ between runs or hosts; every other field is deterministic."""

PARSER = f"ast/{sys.version_info.major}.{sys.version_info.minor}"
"""The syntax the analysis accepts: the standard-library parser of this interpreter version."""


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    runs: int
    source_digest: str
    config_digest: str
    model_revision: str
    counters: dict[str, int]
    samples: tuple[dict[str, Any], ...]
    process_peak_rss_bytes: int | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 4,
            "kind": "deadtrace-benchmark",
            "runs": self.runs,
            "descriptor": {
                "source_digest": self.source_digest,
                "config_digest": self.config_digest,
                "model_revision": self.model_revision,
                "deadtrace_version": __version__,
                "parser": PARSER,
            },
            "host": {
                "system": platform.system(),
                "release": platform.release(),
                "machine": platform.machine(),
                "python_implementation": platform.python_implementation(),
                "python_version": platform.python_version(),
            },
            "counters": dict(sorted(self.counters.items())),
            "samples": list(self.samples),
            "summary": {
                **{
                    stage: _summary([sample[stage] for sample in self.samples])
                    for stage in TOP_LEVEL_STAGES
                },
                "stages": {
                    name: _summary([sample["stages"][name] for sample in self.samples])
                    for name in STAGES
                },
            },
            "process_peak_rss_bytes": self.process_peak_rss_bytes,
            "volatile_fields": list(VOLATILE_FIELDS),
            "notes": {
                "timing": (
                    "total_seconds covers collect, frontend, and solve of one analysis. "
                    "report_seconds measures rendering the JSON semantic report afterwards and "
                    "is not part of total_seconds. Sub-stage seconds are nested inside their "
                    "parent stage and never exceed it."
                ),
                "memory": (
                    "process_peak_rss_bytes is the process lifetime peak reported by the OS; "
                    "timings run without tracemalloc instrumentation."
                ),
                "privacy": (
                    "The artifact contains no paths, source text, symbol names, configuration "
                    "values, user names, or host names."
                ),
            },
        }


def benchmark(scan_path: Path, config: Config, runs: int) -> BenchmarkResult:
    if runs < 1 or runs > 100:
        raise ValueError("benchmark runs must be between 1 and 100")
    samples: list[dict[str, Any]] = []
    descriptor: tuple[str, str, str] | None = None
    counters: dict[str, int] | None = None
    for _ in range(runs):
        result = analyze(scan_path, config)
        report_started = perf_counter()
        render_semantic_json(result)
        report_seconds = perf_counter() - report_started
        current = (result.source_digest, result.config_digest, result.model_revision)
        if descriptor is not None and current != descriptor:
            raise RuntimeError("analysis inputs changed during benchmark")
        descriptor = current
        current_counters = _counters(result)
        if counters is not None and current_counters != counters:
            raise RuntimeError("analysis counters changed between benchmark runs")
        counters = current_counters
        stages = dict(result.metrics.stage_seconds)
        stages["report.render"] = report_seconds
        samples.append(
            {
                "collect_seconds": result.metrics.collect_seconds,
                "frontend_seconds": result.metrics.frontend_seconds,
                "solve_seconds": result.metrics.solve_seconds,
                "report_seconds": report_seconds,
                "total_seconds": result.metrics.total_seconds,
                "stages": stages,
            }
        )
    assert descriptor is not None
    assert counters is not None
    return BenchmarkResult(
        runs,
        descriptor[0],
        descriptor[1],
        descriptor[2],
        counters,
        tuple(samples),
        _process_peak_rss_bytes(),
    )


def render_benchmark_json(result: BenchmarkResult) -> str:
    return render_json_artifact(result.to_dict())


def render_benchmark_text(result: BenchmarkResult) -> str:
    payload = result.to_dict()
    summary = payload["summary"]
    host = payload["host"]
    descriptor = payload["descriptor"]
    lines = [
        f"Deadtrace benchmark ({result.runs} runs)",
        (
            f"Host: {host['system']} {host['release']} {host['machine']} | "
            f"{host['python_implementation']} {host['python_version']}"
        ),
        (
            f"Tool: deadtrace {descriptor['deadtrace_version']} | "
            f"model {descriptor['model_revision']} | parser {descriptor['parser']}"
        ),
        (
            f"Process peak RSS: {result.process_peak_rss_bytes} bytes"
            if result.process_peak_rss_bytes is not None
            else "Process peak RSS: unavailable on this platform"
        ),
    ]
    for stage in TOP_LEVEL_STAGES:
        values = summary[stage]
        lines.append(
            f"{stage}: min={values['min']:.6f}s "
            f"median={values['median']:.6f}s max={values['max']:.6f}s"
        )
    lines.append("Sub-stages (median seconds):")
    lines.extend(f"  {name}: {summary['stages'][name]['median']:.6f}" for name in STAGES)
    lines.append("Counters:")
    lines.extend(f"  {name}: {value}" for name, value in payload["counters"].items())
    return "\n".join(lines) + "\n"


def _counters(result: AnalysisResult) -> dict[str, int]:
    metrics = result.metrics
    return {
        "files": metrics.files,
        "lines": metrics.lines,
        "nodes": metrics.nodes,
        "edges": metrics.edges,
        "worlds": metrics.worlds,
        **metrics.counters,
    }


def _summary(values: list[float]) -> dict[str, float]:
    return {"min": min(values), "median": statistics.median(values), "max": max(values)}


def _process_peak_rss_bytes() -> int | None:
    if os.name == "nt":
        return _windows_peak_working_set_bytes()
    try:
        import importlib

        resource_module = importlib.import_module("resource")
    except ImportError:  # pragma: no cover - only unusual non-POSIX runtimes
        return None
    usage = resource_module.getrusage(resource_module.RUSAGE_SELF)
    peak = int(usage.ru_maxrss)
    return peak if sys.platform == "darwin" else peak * 1024


def _windows_peak_working_set_bytes() -> int | None:
    if sys.platform != "win32":  # pragma: no cover - platform guard
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        get_current_process = kernel32.GetCurrentProcess
        get_current_process.restype = wintypes.HANDLE
        get_process_memory_info = psapi.GetProcessMemoryInfo
        get_process_memory_info.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(ProcessMemoryCounters),
            wintypes.DWORD,
        ]
        get_process_memory_info.restype = wintypes.BOOL
        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        if not get_process_memory_info(get_current_process(), ctypes.byref(counters), counters.cb):
            return None
        return int(counters.PeakWorkingSetSize)
    except (AttributeError, OSError):  # pragma: no cover - defensive platform fallback
        return None
