"""End-to-end static analysis orchestration."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, replace
from hashlib import sha256
from pathlib import Path
from time import perf_counter

from deadtrace.config import Config
from deadtrace.core import AnalysisSnapshot, AssemblyState, Limitation, solve
from deadtrace.deployment import read_deployment_references
from deadtrace.entry_points import read_project_entry_points
from deadtrace.findings import Finding, build_findings
from deadtrace.frameworks import FrameworkModel, build_framework_model
from deadtrace.model import InventoryReport
from deadtrace.pytest_semantics import apply_pytest_model, read_pytest_collection
from deadtrace.python_frontend import PythonProgram, build_python_program
from deadtrace.scanner import (
    SourceCollection,
    collect_sources,
    inventory_collection,
    parse_collection,
)
from deadtrace.target_environment import (
    UNTESTED_VERSION,
    TargetEnvironment,
    read_target_environment,
)
from deadtrace.timing import StageTimings

MODEL_REVISION = "python-fastapi-dishka/30"


@dataclass(frozen=True, slots=True)
class AnalysisMetrics:
    files: int
    lines: int
    nodes: int
    edges: int
    worlds: int
    collect_seconds: float
    frontend_seconds: float
    solve_seconds: float
    total_seconds: float
    stage_seconds: Mapping[str, float] = field(default_factory=dict)
    counters: Mapping[str, int] = field(default_factory=dict)


@dataclass(slots=True)
class AnalysisResult:
    collection: SourceCollection
    inventory: InventoryReport
    program: PythonProgram
    model: FrameworkModel
    snapshot: AnalysisSnapshot
    findings: tuple[Finding, ...]
    source_digest: str
    config_digest: str
    model_revision: str
    target_environment: TargetEnvironment
    metrics: AnalysisMetrics

    @property
    def complete(self) -> bool:
        return bool(self.snapshot.worlds) and all(
            world.assembly_state is AssemblyState.COMPLETE and not world.exhausted_budget
            for world in self.snapshot.worlds
        )

    @property
    def has_operational_errors(self) -> bool:
        return self.inventory.has_errors or any(
            world.assembly_state is AssemblyState.INVALID for world in self.snapshot.worlds
        )


def analyze(scan_path: Path, config: Config) -> AnalysisResult:
    """Run one immutable, read-only analysis snapshot."""

    timings = StageTimings()
    started = perf_counter()
    collection = collect_sources(scan_path, timings=timings, exclude=config.exclude)
    parsed = parse_collection(collection, timings=timings)
    inventory = inventory_collection(collection, config, timings=timings, parsed=parsed)
    collected_at = perf_counter()
    program = build_python_program(
        collection, report_exclude=config.report_exclude, timings=timings, parsed=parsed
    )
    with timings.stage("frontend.entry_points"):
        entry_points, entry_point_issues = read_project_entry_points(collection.root)
    with timings.stage("frontend.deployment"):
        deployment = (
            () if config.worlds else read_deployment_references(collection.root, config.exclude)
        )
    model = build_framework_model(
        program,
        config,
        entry_points=entry_points,
        entry_point_issues=entry_point_issues,
        deployment=deployment,
        timings=timings,
    )
    with timings.stage("frontend.pytest"):
        model = apply_pytest_model(
            program,
            model,
            config,
            plugin_modules=tuple(
                entry_point.target.partition(":")[0]
                for entry_point in entry_points
                if entry_point.group == "pytest11"
            ),
            collection=read_pytest_collection(collection.root),
        )
    with timings.stage("frontend.target_environment"):
        target_environment = read_target_environment(
            collection.root,
            {
                binding.target.split(".", 1)[0]
                for module in program.modules.values()
                for binding in module.imports.values()
            },
        )
    if target_environment.issues:
        model.plans = tuple(
            replace(
                plan,
                assembly_state=(
                    plan.assembly_state
                    if plan.assembly_state is AssemblyState.INVALID
                    or all(issue.code == UNTESTED_VERSION for issue in target_environment.issues)
                    else AssemblyState.PARTIAL
                ),
                limitations=tuple(
                    (
                        *plan.limitations,
                        *(
                            Limitation(
                                code=issue.code,
                                message=issue.message,
                                world=plan.id,
                            )
                            for issue in target_environment.issues
                        ),
                    )
                ),
            )
            for plan in model.plans
        )
    if inventory.issues:
        model.plans = tuple(
            replace(
                plan,
                assembly_state=(
                    AssemblyState.INVALID
                    if plan.assembly_state is AssemblyState.INVALID
                    else AssemblyState.PARTIAL
                ),
                limitations=tuple(
                    (
                        *plan.limitations,
                        *(
                            Limitation(
                                code=issue.code,
                                message=f"{issue.path}: {issue.message}",
                                world=plan.id,
                            )
                            for issue in inventory.issues
                        ),
                    )
                ),
            )
            for plan in model.plans
        )
    frontend_at = perf_counter()
    with timings.stage("solve.reachability"):
        snapshot = solve(model.graph, model.plans, max_steps=config.max_steps)
    with timings.stage("solve.findings"):
        findings = build_findings(program, model, snapshot)
    solved_at = perf_counter()
    timings.count("findings", len(findings))
    metrics = AnalysisMetrics(
        files=len(collection.files),
        lines=sum(unit.source.count("\n") + 1 for unit in collection.units),
        nodes=len(model.graph.nodes),
        edges=len(model.graph.edges),
        worlds=len(snapshot.worlds),
        collect_seconds=collected_at - started,
        frontend_seconds=frontend_at - collected_at,
        solve_seconds=solved_at - frontend_at,
        total_seconds=solved_at - started,
        stage_seconds=timings.frozen_seconds(),
        counters=timings.frozen_counts(),
    )
    return AnalysisResult(
        collection=collection,
        inventory=inventory,
        program=program,
        model=model,
        snapshot=snapshot,
        findings=findings,
        source_digest=_source_digest(collection),
        config_digest=_config_digest(config),
        model_revision=MODEL_REVISION,
        target_environment=target_environment,
        metrics=metrics,
    )


def _source_digest(collection: SourceCollection) -> str:
    canonical = "\n".join(f"{unit.path}:{unit.digest}" for unit in collection.units)
    return sha256(canonical.encode()).hexdigest()


def _config_digest(config: Config) -> str:
    fields = asdict(config)
    if not fields["exclude"]:
        del fields["exclude"]  # configurations without it keep their earlier digest
    canonical = json.dumps(fields, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(canonical.encode()).hexdigest()
