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
    finding_explanations = {
        finding.fingerprint: _finding_explanation(result, finding) for finding in result.findings
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
        "",
    ]
    for world in result.snapshot.worlds:
        lines.append(
            f"World {world.id.key}: assembly={world.assembly_state.value}, "
            f"resolved={len(world.resolved_may_run)}, "
            f"conservative={len(world.conservative_may_run)}"
        )
        lines.extend(limitation_lines(world.limitations, indent="  ", label="limitation "))
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


def _finding_explanation(result: AnalysisResult, finding: Any) -> dict[str, Any]:
    node_map = result.model.graph.node_map()
    member_ids = {
        symbol.id
        for member in finding.members
        for symbol in result.program.symbols.values()
        if symbol.path == member.path
        and symbol.qualified_name == member.qualified_name
        and symbol.kind.value == member.kind
        and symbol.occurrence == member.occurrence
    }
    worlds = []
    for world in result.snapshot.worlds:
        if world.id.key not in finding.worlds:
            continue
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
        worlds.append(
            {
                "world": world.id.key,
                "assembly_state": world.assembly_state.value,
                "negative_findings_allowed": world.negative_findings_allowed,
                "members": states,
                "limitations": [
                    {"code": item.code, "message": item.message} for item in world.limitations
                ],
            }
        )
    reached = set().union(
        *(
            world.resolved_may_run | world.conservative_may_run
            for world in result.snapshot.worlds
            if world.id.key in finding.worlds
        )
    )
    outbound = [
        {
            "source": node_map[edge.source].display_name,
            "target": node_map[edge.target].display_name,
            "kind": edge.kind.value,
            "detail": edge.detail,
        }
        for edge in result.model.graph.edges
        if edge.source in member_ids and edge.target not in member_ids and edge.target in reached
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
