"""Validate independent seed-case manifests against lexical inventory."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from deadtrace.analysis import AnalysisResult, analyze
from deadtrace.artifacts import MAX_ARTIFACT_BYTES, InputTooLargeError, read_bounded_bytes
from deadtrace.config import Config, discover_config, load_config
from deadtrace.core import ReachabilityKind
from deadtrace.scanner import scan


class CaseValidationError(ValueError):
    """Raised for malformed or stale fixture expectations."""


_EXPECTATIONS = frozenset(
    {
        "live",
        "candidate",
        "protected",
        "not_candidate",
        "unknown",
        "test_only",
        "test_live",
    }
)
"""``not_candidate`` is a safety-only expectation: the target is in no finding."""


@dataclass(frozen=True, slots=True)
class CaseValidationResult:
    cases: int
    targets: int
    semantic_cases: int = 0


def validate_cases(root: Path) -> CaseValidationResult:
    """Validate CASE.md/CASE.toml presence and every lexical target."""

    manifests = sorted(root.rglob("CASE.toml"))
    if not manifests:
        raise CaseValidationError(f"no CASE.toml manifests found under {root}")
    target_count = 0
    semantic_count = 0
    case_ids: set[str] = set()
    for manifest in manifests:
        case_dir = manifest.parent
        if not (case_dir / "CASE.md").is_file():
            raise CaseValidationError(f"missing CASE.md beside {manifest}")
        document = _read_manifest(manifest)
        case_id = _required_string(document, "case_id", manifest)
        if case_id in case_ids:
            raise CaseValidationError(f"duplicate case_id {case_id!r}")
        case_ids.add(case_id)
        targets = document.get("targets")
        if not isinstance(targets, list) or not targets:
            raise CaseValidationError(f"{manifest}: targets must be a non-empty array of tables")
        report = scan(case_dir, Config())
        identities = {
            (definition.path, definition.kind.value, definition.qualified_name)
            for definition in report.definitions
        }
        for target in targets:
            if not isinstance(target, dict):
                raise CaseValidationError(f"{manifest}: each target must be a table")
            identity = (
                _required_string(target, "path", manifest),
                _required_string(target, "kind", manifest),
                _required_string(target, "qualified_name", manifest),
            )
            expectation = _required_string(target, "expectation", manifest)
            if expectation not in _EXPECTATIONS:
                raise CaseValidationError(f"{manifest}: unsupported expectation {expectation!r}")
            if identity not in identities:
                raise CaseValidationError(f"{manifest}: lexical target not found: {identity!r}")
            target_count += 1
        analysis_expectation = document.get("analysis")
        if analysis_expectation is not None:
            if not isinstance(analysis_expectation, dict):
                raise CaseValidationError(f"{manifest}: analysis must be a table")
            result = analyze(
                case_dir,
                load_config(discover_config(case_dir, None)),
            )
            _validate_analysis(result, analysis_expectation, targets, manifest)
            semantic_count += 1
    return CaseValidationResult(
        cases=len(manifests), targets=target_count, semantic_cases=semantic_count
    )


def unmet_targets(case_dir: Path) -> tuple[str, ...]:
    """Return ``path:qualified_name`` of every target whose expectation the analysis misses.

    The case must pass ``validate_cases``, so a case that records a known violation has no
    ``[analysis]`` table. Every target is then checked against the analysis instead of stopping at
    the first unmet one, which lets a test track exactly which expectations are still violated.
    """

    validate_cases(case_dir)
    manifest = case_dir / "CASE.toml"
    targets = _read_manifest(manifest)["targets"]
    result = analyze(case_dir, load_config(discover_config(case_dir, None)))
    unmet: list[str] = []
    for target in targets:
        try:
            _validate_semantic_target(result, target, manifest)
        except CaseValidationError:
            unmet.append(f"{target['path']}:{target['qualified_name']}")
    return tuple(sorted(unmet))


def _validate_analysis(
    result: AnalysisResult,
    expectation: dict[str, Any],
    targets: list[Any],
    manifest: Path,
) -> None:
    unknown = sorted(set(expectation) - {"complete", "worlds", "finding_codes", "limitation_codes"})
    if unknown:
        raise CaseValidationError(f"{manifest}: unknown analysis option(s): {', '.join(unknown)}")
    complete = expectation.get("complete")
    if not isinstance(complete, bool):
        raise CaseValidationError(f"{manifest}: analysis.complete must be a boolean")
    if result.complete is not complete:
        raise CaseValidationError(
            f"{manifest}: expected complete={complete}, got complete={result.complete}"
        )
    _expect_string_set(
        manifest,
        "analysis.worlds",
        expectation.get("worlds"),
        {world.id.key for world in result.snapshot.worlds},
    )
    _expect_string_set(
        manifest,
        "analysis.finding_codes",
        expectation.get("finding_codes"),
        {finding.code for finding in result.findings},
    )
    _expect_string_set(
        manifest,
        "analysis.limitation_codes",
        expectation.get("limitation_codes"),
        {limitation.code for world in result.snapshot.worlds for limitation in world.limitations},
    )
    for target in targets:
        assert isinstance(target, dict)
        _validate_semantic_target(result, target, manifest)


def _expect_string_set(
    manifest: Path,
    label: str,
    expected: object,
    actual: set[str],
) -> None:
    if not isinstance(expected, list) or not all(isinstance(item, str) for item in expected):
        raise CaseValidationError(f"{manifest}: {label} must be an array of strings")
    if set(expected) != actual:
        raise CaseValidationError(
            f"{manifest}: {label} expected {sorted(expected)!r}, got {sorted(actual)!r}"
        )


def _validate_semantic_target(
    result: AnalysisResult,
    target: dict[str, Any],
    manifest: Path,
) -> None:
    path = _required_string(target, "path", manifest)
    qualified_name = _required_string(target, "qualified_name", manifest)
    expectation = _required_string(target, "expectation", manifest)
    symbol = next(
        (
            item
            for item in result.program.symbols.values()
            if item.path == path and item.qualified_name == qualified_name
        ),
        None,
    )
    if symbol is None:
        raise CaseValidationError(f"{manifest}: semantic target not found: {path}:{qualified_name}")
    production = tuple(world for world in result.snapshot.worlds if world.id.profile != "tests")
    tests = tuple(world for world in result.snapshot.worlds if world.id.profile == "tests")
    production_states = {world.state_of(symbol.id) for world in production}
    test_states = {world.state_of(symbol.id) for world in tests}
    finding_codes = {
        finding.code
        for finding in result.findings
        if any(
            member.path == path and member.qualified_name == qualified_name
            for member in finding.members
        )
    }
    valid = {
        "live": ReachabilityKind.RESOLVED in production_states,
        "candidate": bool(finding_codes & {"RCH001", "RCH002", "RCH003"}),
        "protected": (
            ReachabilityKind.CONSERVATIVE in production_states
            or any(symbol.id in world.retained for world in production)
        )
        and not finding_codes,
        "not_candidate": not finding_codes,
        "unknown": any(not world.negative_findings_allowed for world in production)
        and not finding_codes,
        "test_only": (
            ReachabilityKind.RESOLVED in test_states
            and ReachabilityKind.RESOLVED not in production_states
            and "RCH004" in finding_codes
        ),
        "test_live": (
            ReachabilityKind.RESOLVED in test_states
            and ReachabilityKind.RESOLVED not in production_states
            and not finding_codes
        ),
    }
    if not valid[expectation]:
        raise CaseValidationError(
            f"{manifest}: target {path}:{qualified_name} did not satisfy {expectation!r}"
        )
    expected_worlds = target.get("worlds")
    if expected_worlds is not None:
        if not isinstance(expected_worlds, list) or not all(
            isinstance(item, str) for item in expected_worlds
        ):
            raise CaseValidationError(f"{manifest}: target.worlds must be an array of strings")
        if expectation in {"live", "test_live", "test_only"}:
            actual_worlds = {
                world.id.key
                for world in result.snapshot.worlds
                if world.state_of(symbol.id) is ReachabilityKind.RESOLVED
            }
        else:
            actual_worlds = {
                world.id.key
                for world in result.snapshot.worlds
                if world.state_of(symbol.id) is not None or symbol.id in world.retained
            }
        if set(expected_worlds) != actual_worlds:
            raise CaseValidationError(
                f"{manifest}: target {path}:{qualified_name} worlds expected "
                f"{sorted(expected_worlds)!r}, got {sorted(actual_worlds)!r}"
            )


def _read_manifest(path: Path) -> dict[str, Any]:
    try:
        document = tomllib.loads(read_bounded_bytes(path, limit=MAX_ARTIFACT_BYTES).decode("utf-8"))
    except (
        OSError,
        UnicodeError,
        InputTooLargeError,
        RecursionError,
        tomllib.TOMLDecodeError,
    ) as error:
        raise CaseValidationError(f"cannot read {path}: {error}") from error
    if document.get("schema_version") != 1:
        raise CaseValidationError(f"{path}: schema_version must be 1")
    return document


def _required_string(document: dict[str, Any], key: str, path: Path) -> str:
    value = document.get(key)
    if not isinstance(value, str) or not value:
        raise CaseValidationError(f"{path}: {key} must be a non-empty string")
    return value
