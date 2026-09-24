"""Privacy-conscious troubleshooting artifacts without project source or symbol names."""

from __future__ import annotations

from collections import Counter
from typing import Any

from deadtrace import __version__
from deadtrace.analysis import AnalysisResult
from deadtrace.artifacts import render_json_artifact


def troubleshooting_bundle(result: AnalysisResult) -> dict[str, Any]:
    """Project an analysis into aggregated support data safe to inspect before sharing."""

    return {
        "schema_version": 1,
        "kind": "deadtrace-troubleshooting-bundle",
        "tool": {"name": "deadtrace", "version": __version__},
        "analysis_state": "complete" if result.complete else "incomplete",
        "descriptor": {
            "source_digest": result.source_digest,
            "config_digest": result.config_digest,
            "model_revision": result.model_revision,
            "target_environment_digest": result.target_environment.digest,
        },
        "inputs": {
            "files": result.metrics.files,
            "lines": result.metrics.lines,
            "issue_counts": _counts(issue.code for issue in result.inventory.issues),
        },
        "target_environment": {
            "packages": [
                {"name": item.name, "version": item.version, "source": item.source}
                for item in result.target_environment.packages
            ],
            "issue_counts": _counts(issue.code for issue in result.target_environment.issues),
        },
        "capabilities": [
            {"id": item.id, "revision": item.revision, "status": item.status}
            for item in result.model.capabilities
        ],
        "worlds": [
            {
                "id": world.id.key,
                "assembly_state": world.assembly_state.value,
                "negative_findings_allowed": world.negative_findings_allowed,
                "resolved_count": len(world.resolved_may_run),
                "conservative_count": len(world.conservative_may_run),
                "retained_count": len(world.retained),
                "limitation_counts": _counts(item.code for item in world.limitations),
            }
            for world in result.snapshot.worlds
        ],
        "findings": {
            "total": len(result.findings),
            "counts": _counts(item.code for item in result.findings),
        },
        "privacy": {
            "included": [
                "content digests",
                "dependency names and exact detected versions",
                "world identifiers",
                "capability states",
                "aggregated issue, limitation, and finding codes",
            ],
            "omitted": [
                "source text",
                "absolute project root",
                "file paths",
                "symbol names",
                "configuration values",
                "environment variables",
                "object values",
            ],
        },
    }


def render_troubleshooting_json(result: AnalysisResult) -> str:
    return render_json_artifact(troubleshooting_bundle(result))


def render_troubleshooting_text(result: AnalysisResult) -> str:
    payload = troubleshooting_bundle(result)
    inputs = payload["inputs"]
    findings = payload["findings"]
    assert isinstance(inputs, dict)
    assert isinstance(findings, dict)
    return (
        "Deadtrace troubleshooting bundle preview\n"
        f"Analysis: {payload['analysis_state']} | files={inputs['files']} | "
        f"lines={inputs['lines']} | findings={findings['total']}\n"
        f"Model revision: {result.model_revision}\n"
        f"Worlds: {len(result.snapshot.worlds)} | capabilities={len(result.model.capabilities)}\n"
        "Contains aggregate diagnostics and digests; omits source, paths, symbols, config values, "
        "environment variables, and object values.\n"
    )


def _counts(values: Any) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))
