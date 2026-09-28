"""Versioned report projection for semantic analysis."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable
from typing import Any

from deadtrace import __version__
from deadtrace.analysis import AnalysisResult
from deadtrace.core import Derivation, Limitation, NodeId

REPORT_SCHEMA_VERSION = 1
_EXPLANATION_LIMIT = 2_000


def semantic_report_dict(result: AnalysisResult) -> dict[str, Any]:
    node_map = result.model.graph.node_map()
    derivations = sorted(
        (
            _derivation_dict(derivation, node_map)
            for world in result.snapshot.worlds
            for derivation in world.derivations
        ),
        key=lambda item: (
            item["world"],
            item["target"],
            item["reachability"],
            item["kind"],
        ),
    )
    shown_derivations = derivations[:_EXPLANATION_LIMIT]
    explainer = _FindingExplainer(result)
    finding_explanations = {
        finding.fingerprint: explainer.explain(finding) for finding in result.findings
    }
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "analysis_state": "complete" if result.complete else "incomplete",
        "validation": "not_performed",
        "tool": {"name": "deadtrace", "version": __version__},
        "descriptor": {
            "source_digest": result.source_digest,
            "config_digest": result.config_digest,
            "model_revision": result.model_revision,
            "target_environment_digest": result.target_environment.digest,
        },
        "source_universe": {
            "root": str(result.collection.root),
            "files": list(result.collection.files),
            "skipped_directories": list(result.collection.skipped_directories),
            "excluded_files": list(result.collection.excluded_files),
        },
        "inventory": {
            "definitions": [item.to_dict() for item in result.inventory.definitions],
            "definition_count": len(result.inventory.definitions),
        },
        "capabilities": [
            {"id": item.id, "revision": item.revision, "status": item.status}
            for item in result.model.capabilities
        ],
        "target_environment": result.target_environment.to_dict(),
        "worlds": [_world_dict(world, node_map) for world in result.snapshot.worlds],
        "issues": [issue.to_dict() for issue in result.inventory.issues],
        "findings": [finding.to_dict() for finding in result.findings],
        "explanations": {
            "derivations": shown_derivations,
            "total": len(derivations),
            "truncated": len(shown_derivations) < len(derivations),
            "findings": finding_explanations,
        },
        "metrics": {
            "files": result.metrics.files,
            "lines": result.metrics.lines,
            "nodes": result.metrics.nodes,
            "edges": result.metrics.edges,
            "worlds": result.metrics.worlds,
        },
        "summary": {
            "finding_count": len(result.findings),
            "candidate_count": sum(item.code == "RCH001" for item in result.findings),
            "binding_review_count": sum(item.code == "RCH003" for item in result.findings),
            "blocker_count": sum(
                world.assembly_state.value != "complete" for world in result.snapshot.worlds
            ),
        },
    }


def render_semantic_json(result: AnalysisResult) -> str:
    return (
        json.dumps(semantic_report_dict(result), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    )


def render_semantic_text(result: AnalysisResult) -> str:
    state = "complete" if result.complete else "incomplete"
    lines = [
        f"Deadtrace analysis ({state}, validation=not_performed)",
        f"Root: {result.collection.root}",
        (
            f"Files: {result.metrics.files} | Lines: {result.metrics.lines} "
            f"| Worlds: {result.metrics.worlds} | Findings: {len(result.findings)}"
        ),
        *_skipped_directory_lines(result.collection.skipped_directories),
        *(
            [f"Excluded by configuration: {len(result.collection.excluded_files)} files"]
            if result.collection.excluded_files
            else []
        ),
        "",
    ]
    shared = _shared_limitations(result)
    if shared and len(result.snapshot.worlds) > 1:
        lines.append("Every world:")
        lines.extend(limitation_lines(shared, indent="  ", label="limitation "))
    for world in result.snapshot.worlds:
        lines.append(
            f"World {world.id.key}: assembly={world.assembly_state.value}, "
            f"resolved={len(world.resolved_may_run)}, "
            f"conservative={len(world.conservative_may_run)}"
        )
        own = (
            [item for item in world.limitations if _limitation_key(item) not in shared_keys]
            if (shared_keys := {_limitation_key(item) for item in shared})
            and len(result.snapshot.worlds) > 1
            else list(world.limitations)
        )
        lines.extend(limitation_lines(own, indent="  ", label="limitation "))
    lines.extend(_protection_lines(result))
    if result.findings:
        lines.append("")
        for finding in result.findings:
            lines.append(f"{finding.code} {finding.fingerprint}  {finding.title}")
            lines.append(f"  {finding.reason}")
            for member in finding.members:
                lines.append(f"  {member.path}:{member.line}  {member.qualified_name}")
    else:
        lines.extend(["", "No review findings were emitted."])
    lines.extend(
        [
            "",
            "A review finding is not a claim that deletion is safe.",
        ]
    )
    return "\n".join(lines) + "\n"


def _limitation_key(limitation: Limitation) -> tuple[str, str, str]:
    return (limitation.code, limitation.message, str(limitation.origin or ""))


def _shared_limitations(result: AnalysisResult) -> list[Limitation]:
    """Limitations every world has, such as a file that cannot be read; shown once in text."""

    worlds = result.snapshot.worlds
    if not worlds:
        return []
    common = {_limitation_key(item) for item in worlds[0].limitations}
    for world in worlds[1:]:
        common &= {_limitation_key(item) for item in world.limitations}
    common = {key for key in common if key[0] != GUARD_CODE}
    seen: set[tuple[str, str, str]] = set()
    shared: list[Limitation] = []
    for item in worlds[0].limitations:
        key = _limitation_key(item)
        if key in common and key not in seen:
            seen.add(key)
            shared.append(item)
    return shared


PROTECTION_SHARE_SHOWN = 0.2
"""Explain the widest guards when at least this share of production definitions is protected
only conservatively; below it, the findings speak for themselves."""


def widest_guards(result: AnalysisResult, limit: int) -> list[tuple[int, str, str]]:
    """Unknown boundaries of production worlds by how much code they alone keep possibly running.

    Each definition that production worlds reach only conservatively is attributed to the
    boundary its derivation crossed first from resolved code, so a dynamic import that makes
    modules run is credited with what their decorators and calls reach in turn. An entry is the
    number of definitions attributed to a boundary, its reason, and where it is: the places to
    model, configure roots around, or declare as keep contracts when a scan reports little.
    """

    node_map = result.model.graph.node_map()
    reasons: dict[tuple[NodeId, str], str] = {}
    for boundary in (
        *result.model.graph.boundaries,
        *(boundary for plan in result.model.plans for boundary in plan.boundaries),
    ):
        reasons.setdefault((boundary.source, boundary.domain), boundary.reason)
    production = [world for world in result.snapshot.worlds if world.id.profile != "tests"]
    resolved = set().union(*(world.resolved_may_run for world in production))
    widths: dict[tuple[NodeId, str], int] = {}
    for world in production:
        counts: dict[tuple[NodeId, str], int] = {}
        for node_id, cause in _first_boundaries(world).items():
            if cause is None or node_id in resolved or node_map[node_id].kind.value == "module":
                continue
            counts[cause] = counts.get(cause, 0) + 1
        for cause, count in counts.items():
            widths[cause] = max(widths.get(cause, 0), count)
    ranked = sorted(widths.items(), key=lambda item: (-item[1], str(item[0][0]), item[0][1]))
    prefix = "unknown execution boundary: "
    return [
        (
            width,
            reasons.get((origin, detail.removeprefix(prefix)), detail.removeprefix(prefix)),
            f"{node_map[origin].path}:{node_map[origin].line}",
        )
        for (origin, detail), width in ranked[:limit]
    ]


def _first_boundaries(world: Any) -> dict[NodeId, tuple[NodeId, str] | None]:
    """For each conservative node, the boundary its first derivation crossed from resolved code."""

    first: dict[NodeId, Derivation] = {}
    for derivation in world.derivations:
        if derivation.reachability.value == "conservative_may_run":
            first.setdefault(derivation.target, derivation)
    causes: dict[NodeId, tuple[NodeId, str] | None] = {}
    for start in world.conservative_may_run:
        path: list[NodeId] = []
        node: NodeId | None = start
        cause: tuple[NodeId, str] | None = None
        while node is not None and node not in causes:
            derivation = first.get(node)
            if derivation is None or derivation.source is None:
                break
            path.append(node)
            if derivation.source in world.resolved_may_run:
                if derivation.kind.value == "unknown":
                    cause = (derivation.source, derivation.detail)
                break
            node = derivation.source if derivation.source not in path else None
        else:
            if node is not None:
                cause = causes[node]
        for item in path:
            causes[item] = cause
        causes.setdefault(start, cause)
    return causes


def _protection_lines(result: AnalysisResult) -> list[str]:
    production = [world for world in result.snapshot.worlds if world.id.profile != "tests"]
    if not production:
        return []
    definitions = [node for node in result.model.graph.nodes if node.kind.value != "module"]
    resolved = set().union(*(world.resolved_may_run for world in production))
    conservative = set().union(*(world.conservative_may_run for world in production)) - resolved
    protected = sum(1 for node in definitions if node.id in conservative)
    if not definitions or protected / len(definitions) < PROTECTION_SHARE_SHOWN:
        return []
    lines = [
        "",
        (
            f"{protected} of {len(definitions)} definitions may run only through unknown "
            "boundaries, so they cannot be reported. The widest guards:"
        ),
    ]
    lines.extend(
        f"  {location}  {message} ({width} definitions)"
        for width, message, location in widest_guards(result, 5)
    )
    lines.append(
        "  Configure [[tool.deadtrace.worlds]] roots to leave development scripts out, or declare "
        "[[tool.deadtrace.keep]] contracts for code loaded by name."
    )
    return lines


def _skipped_directory_lines(skipped: tuple[str, ...], shown: int = 5) -> list[str]:
    """Name the skipped environments and tool directories; hidden ones are only counted."""

    visible = [
        path
        for path in skipped
        if not path.rpartition("/")[2].startswith(".") and not path.endswith("__pycache__")
    ]
    if not visible:
        return []
    names = ", ".join(visible[:shown])
    more = f" and {len(visible) - shown} more" if len(visible) > shown else ""
    return [f"Skipped environments and tool directories: {names}{more}"]


def explain_fingerprint(report: dict[str, Any], fingerprint: str) -> str:
    findings = report.get("findings")
    if not isinstance(findings, list):
        raise ValueError("report does not contain a findings array")
    for finding in findings:
        if isinstance(finding, dict) and finding.get("fingerprint") == fingerprint:
            explanations = report.get("explanations")
            if isinstance(explanations, dict):
                finding_explanations = explanations.get("findings")
                if isinstance(finding_explanations, dict):
                    explanation = finding_explanations.get(fingerprint)
                    if isinstance(explanation, dict):
                        return (
                            json.dumps(
                                explanation,
                                ensure_ascii=False,
                                indent=2,
                                sort_keys=True,
                            )
                            + "\n"
                        )
            return json.dumps(finding, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    raise KeyError(fingerprint)


def doctor_text(result: AnalysisResult) -> str:
    lines = [
        "Deadtrace doctor",
        f"Source digest: {result.source_digest}",
        f"Config digest: {result.config_digest}",
        f"Model revision: {result.model_revision}",
        "Capabilities:",
    ]
    lines.extend(
        f"  {capability.id}@{capability.revision}: {capability.status}"
        for capability in result.model.capabilities
    )
    lines.append("Worlds:")
    for world in result.snapshot.worlds:
        lines.append(f"  {world.id.key}: {world.assembly_state.value}")
        lines.extend(limitation_lines(world.limitations, indent="    ", label=""))
    guards = widest_guards(result, 10)
    if guards:
        lines.append("Widest guards (definitions only they keep possibly running):")
        lines.extend(f"  {width:6d}  {location}  {message}" for width, message, location in guards)
    return "\n".join(lines) + "\n"


GUARD_CODE = "DT2002"
GUARD_KINDS_SHOWN = 5
"""Up to this many kinds of conservative guard are listed; more are summarized."""


def limitation_lines(limitations: Iterable[Limitation], *, indent: str, label: str) -> list[str]:
    """A world's limitations for text output, identical ones counted once.

    Every limitation other than a conservative guard (``DT2002``) is listed. Guards are listed by
    kind when there are few; otherwise one line gives their number and the most common kinds,
    and the JSON report keeps each of them.
    """

    counts = Counter((item.code, item.message) for item in limitations)
    head = f"{indent}{label}"
    lines = [
        _counted(f"{head}{code}: {message}", count)
        for (code, message), count in counts.items()
        if code != GUARD_CODE
    ]
    guards = sorted(
        ((count, message) for (code, message), count in counts.items() if code == GUARD_CODE),
        key=lambda item: (-item[0], item[1]),
    )
    if len(guards) <= GUARD_KINDS_SHOWN:
        lines.extend(_counted(f"{head}{GUARD_CODE}: {message}", count) for count, message in guards)
        return lines
    total = sum(count for count, _message in guards)
    lines.append(
        f"{head}{GUARD_CODE}: {total} conservative guards of {len(guards)} kinds protect code"
        " that may run; the most common:"
    )
    lines.extend(_counted(f"{indent}    {message}", count) for count, message in guards[:3])
    lines.append(f"{indent}    and {len(guards) - 3} more kinds; the JSON report lists every guard")
    return lines


def _counted(line: str, count: int) -> str:
    return f"{line} (x{count})" if count > 1 else line


def _world_dict(world: Any, node_map: dict[NodeId, Any]) -> dict[str, Any]:
    return {
        "id": {"profile": world.id.profile, "scenario": world.id.scenario},
        "assembly_state": world.assembly_state.value,
        "roots": sorted(node_map[item].display_name for item in world.roots),
        "root_provenance": [
            {
                "target": node_map[item.target].display_name,
                "kind": item.kind,
                "detail": item.detail,
            }
            for item in world.root_provenance
        ],
        "retained_roots": sorted(node_map[item].display_name for item in world.retained_roots),
        "conservative_roots": sorted(
            node_map[item].display_name for item in world.conservative_roots
        ),
        "resolved_may_run": sorted(node_map[item].display_name for item in world.resolved_may_run),
        "conservative_may_run": sorted(
            node_map[item].display_name for item in world.conservative_may_run
        ),
        "retained_declarations": sorted(node_map[item].display_name for item in world.retained),
        "limitations": [
            {
                "code": item.code,
                "message": item.message,
                "origin": node_map[item.origin].display_name if item.origin in node_map else None,
            }
            for item in world.limitations
        ],
        "negative_findings_allowed": world.negative_findings_allowed,
    }


def _derivation_dict(derivation: Derivation, node_map: dict[NodeId, Any]) -> dict[str, str | None]:
    return {
        "world": derivation.world.key,
        "target": node_map[derivation.target].display_name,
        "reachability": derivation.reachability.value,
        "kind": derivation.kind.value,
        "source": (
            node_map[derivation.source].display_name if derivation.source in node_map else None
        ),
        "detail": derivation.detail,
    }


class _FindingExplainer:
    """Explains findings with indexes built once per report, not once per finding."""

    def __init__(self, result: AnalysisResult) -> None:
        self.result = result
        self.node_map = result.model.graph.node_map()
        self.symbols: dict[tuple[str, str, str, int], NodeId] = {
            (symbol.path, symbol.qualified_name, symbol.kind.value, symbol.occurrence): symbol.id
            for symbol in result.program.symbols.values()
        }
        self.outbound: dict[NodeId, list[Any]] = {}
        for edge in result.model.graph.edges:
            self.outbound.setdefault(edge.source, []).append(edge)

    def explain(self, finding: Any) -> dict[str, Any]:
        node_map = self.node_map
        member_ids = {
            node_id
            for member in finding.members
            if (
                node_id := self.symbols.get(
                    (member.path, member.qualified_name, member.kind, member.occurrence)
                )
            )
            is not None
        }
        worlds = []
        selected = [
            world for world in self.result.snapshot.worlds if world.id.key in finding.worlds
        ]
        for world in selected:
            states = []
            for node_id in sorted(member_ids):
                state = world.state_of(node_id)
                states.append(
                    {
                        "member": node_map[node_id].display_name,
                        "body_state": state.value if state is not None else "not_reached",
                        "retained": node_id in world.retained,
                    }
                )
            # A guard keeps code possibly running, so none reaches an unreached member; the
            # world's entry in the report lists each of them.
            limitations = Counter(
                (item.code, item.message) for item in world.limitations if item.code != GUARD_CODE
            )
            worlds.append(
                {
                    "world": world.id.key,
                    "assembly_state": world.assembly_state.value,
                    "negative_findings_allowed": world.negative_findings_allowed,
                    "members": states,
                    "limitations": [
                        {"code": code, "message": message, "count": count}
                        for (code, message), count in sorted(limitations.items())
                    ],
                    "guard_count": sum(item.code == GUARD_CODE for item in world.limitations),
                }
            )
        reached = set().union(
            *(world.resolved_may_run | world.conservative_may_run for world in selected)
        )
        outbound = [
            {
                "source": node_map[edge.source].display_name,
                "target": node_map[edge.target].display_name,
                "kind": edge.kind.value,
                "detail": edge.detail,
            }
            for source in member_ids
            for edge in self.outbound.get(source, ())
            if edge.target not in member_ids and edge.target in reached
        ]
        shown_outbound = sorted(
            outbound,
            key=lambda item: (item["source"], item["target"], item["kind"], item["detail"]),
        )[:100]
        return {
            "finding": finding.to_dict(),
            "world_states": worlds,
            "live_boundaries": shown_outbound,
            "live_boundaries_truncated": len(shown_outbound) < len(outbound),
            "note": "A review finding is not a claim that deletion is safe.",
        }
