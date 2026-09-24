"""Bounded sub-stage timings and counters for one analysis run.

The collector is additive instrumentation only. It never changes what a stage computes, it holds a
fixed set of keys so artifacts keep a deterministic shape, and it does not use ``tracemalloc``.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from time import perf_counter
from types import MappingProxyType
from typing import Final

STAGES: Final[tuple[str, ...]] = (
    "collect.discover",
    "collect.read",
    "collect.verify_discover",
    "collect.verify_read",
    "collect.parse",
    "collect.inventory_visit",
    "frontend.parse",
    "frontend.symbols",
    "frontend.imports",
    "frontend.declaration_flow",
    "frontend.class_fields",
    "frontend.symbol_flow",
    "frontend.graph",
    "frontend.entry_points",
    "frontend.frameworks_discover",
    "frontend.frameworks_plans",
    "frontend.frameworks_graph",
    "frontend.pytest",
    "frontend.target_environment",
    "solve.reachability",
    "solve.findings",
    "report.render",
)
"""Sub-stage names, prefixed by the top-level stage whose wall time contains them.

``collect.parse`` covers the single ``ast`` parse of every module;
inventory, symbol collection, imports, and framework discovery reuse that result.
``frontend.parse`` is only non-zero when ``build_python_program`` is called without a shared
parse. ``report.render`` runs after the analysis and is measured by the benchmark, not by
``analyze``.
"""

COUNTERS: Final[tuple[str, ...]] = (
    "collect.attempts",
    "collect.files_read",
    "collect.characters",
    "collect.read_errors",
    "frontend.modules",
    "frontend.parse_failures",
    "frontend.symbols",
    "frontend.import_bindings",
    "frontend.edges",
    "frontend.boundaries",
    "frameworks.edges",
    "frameworks.requirements",
    "graph.requirements",
    "graph.boundaries",
    "findings",
)
"""Size counters that are identical for identical source, configuration, and model revision."""


@dataclass(slots=True)
class StageTimings:
    seconds: dict[str, float] = field(default_factory=lambda: dict.fromkeys(STAGES, 0.0))
    counts: dict[str, int] = field(default_factory=lambda: dict.fromkeys(COUNTERS, 0))

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        """Add the wall time of the enclosed block to a known sub-stage."""

        if name not in self.seconds:
            raise KeyError(f"unknown stage {name!r}")
        started = perf_counter()
        try:
            yield
        finally:
            self.seconds[name] += perf_counter() - started

    def count(self, name: str, amount: int = 1) -> None:
        """Add to a known counter."""

        if name not in self.counts:
            raise KeyError(f"unknown counter {name!r}")
        self.counts[name] += amount

    def frozen_seconds(self) -> Mapping[str, float]:
        return MappingProxyType(dict(self.seconds))

    def frozen_counts(self) -> Mapping[str, int]:
        return MappingProxyType(dict(self.counts))
