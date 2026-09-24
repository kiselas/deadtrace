"""Compare two saved semantic reports without re-running analysis."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from deadtrace.artifacts import ArtifactError, render_json_artifact


class Comparability(StrEnum):
    COMPARABLE = "comparable"
    PARTIALLY_COMPARABLE = "partially_comparable"
    INCOMPARABLE = "incomparable"


@dataclass(frozen=True, slots=True)
class ReportComparison:
    status: Comparability
    reasons: tuple[str, ...]
    added: tuple[dict[str, Any], ...]
    resolved: tuple[dict[str, Any], ...]
    unchanged: tuple[dict[str, Any], ...]
    changed: tuple[dict[str, str], ...]
    new_limitations: tuple[dict[str, Any], ...]
    resolved_limitations: tuple[dict[str, Any], ...]
    added_source_files: tuple[str, ...]
    removed_source_files: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "kind": "deadtrace-report-comparison",
            "comparability": self.status.value,
            "reasons": list(self.reasons),
            "findings": {
                "added": list(self.added),
                "resolved": list(self.resolved),
                "unchanged": list(self.unchanged),
                "changed": list(self.changed),
            },
            "limitations": {
                "added": list(self.new_limitations),
                "resolved": list(self.resolved_limitations),
            },
            "source_universe": {
                "added_files": list(self.added_source_files),
                "removed_files": list(self.removed_source_files),
            },
            "summary": {
                "added_findings": len(self.added),
                "resolved_findings": len(self.resolved),
                "unchanged_findings": len(self.unchanged),
                "changed_groups": len(self.changed),
                "new_limitations": len(self.new_limitations),
                "resolved_limitations": len(self.resolved_limitations),
                "added_source_files": len(self.added_source_files),
                "removed_source_files": len(self.removed_source_files),
            },
        }


def validate_semantic_report(payload: dict[str, Any]) -> None:
    """Validate the stable fields consumed by comparison and baseline workflows."""

    if payload.get("schema_version") != 1:
        raise ArtifactError("semantic report schema_version must be 1")
    tool = payload.get("tool")
    if (
        not isinstance(tool, dict)
        or tool.get("name") != "deadtrace"
        or not isinstance(tool.get("version"), str)
    ):
        raise ArtifactError("artifact is not a Deadtrace semantic report")
    if payload.get("analysis_state") not in {"complete", "incomplete"}:
        raise ArtifactError("semantic report analysis_state must be complete or incomplete")
    for key in ("descriptor", "source_universe"):
        if not isinstance(payload.get(key), dict):
            raise ArtifactError(f"semantic report {key} must be an object")
    for key in ("capabilities", "worlds", "findings"):
        if not isinstance(payload.get(key), list):
            raise ArtifactError(f"semantic report {key} must be an array")
    if not isinstance(payload.get("issues", []), list):
        raise ArtifactError("semantic report issues must be an array")
    fingerprints: set[str] = set()
    for finding in payload["findings"]:
        if not isinstance(finding, dict) or not isinstance(finding.get("fingerprint"), str):
            raise ArtifactError("every finding must have a string fingerprint")
        fingerprint = finding["fingerprint"]
        if fingerprint in fingerprints:
            raise ArtifactError(f"duplicate semantic report fingerprint: {fingerprint}")
        fingerprints.add(fingerprint)


def method_descriptor(payload: dict[str, Any]) -> dict[str, Any]:
    """Return the analysis-method fields that determine report comparability."""

    validate_semantic_report(payload)
    tool = payload["tool"]
    descriptor = payload["descriptor"]
    assert isinstance(tool, dict)
    assert isinstance(descriptor, dict)
    worlds = payload["worlds"]
    capabilities = payload["capabilities"]
    assert isinstance(worlds, list)
    assert isinstance(capabilities, list)
    return {
        "schema_version": payload["schema_version"],
        "tool_version": tool.get("version"),
        "model_revision": descriptor.get("model_revision"),
        "config_digest": descriptor.get("config_digest"),
        "target_environment_digest": descriptor.get("target_environment_digest"),
        "analysis_state": payload.get("analysis_state"),
        "input_issues": sorted(
            (
                issue.get("code"),
                issue.get("path"),
            )
            for issue in payload.get("issues", [])
            if isinstance(issue, dict)
        ),
        "worlds": [
            {
                "id": world.get("id"),
                "roots": world.get("roots"),
                "root_provenance": world.get("root_provenance"),
                "retained_roots": world.get("retained_roots"),
                "conservative_roots": world.get("conservative_roots"),
            }
            for world in worlds
            if isinstance(world, dict)
        ],
        "capabilities": capabilities,
    }


def compare_reports(before: dict[str, Any], after: dict[str, Any]) -> ReportComparison:
    """Compare reports while keeping method changes separate from source changes."""

    before_method = method_descriptor(before)
    after_method = method_descriptor(after)
    method_reasons = list(_method_change_reasons(before_method, after_method))
    incomplete = (
        before_method["analysis_state"] != "complete"
        or after_method["analysis_state"] != "complete"
    )
    if incomplete:
        method_reasons.append("one or both analyses are incomplete")
    before_world_ids = _world_ids(before_method)
    after_world_ids = _world_ids(after_method)
    incomparable_reasons: list[str] = []
    if not before_world_ids.intersection(after_world_ids):
        incomparable_reasons.append("reports have no common execution world")
    reasons = tuple(dict.fromkeys((*incomparable_reasons, *method_reasons)))
    status = (
        Comparability.INCOMPARABLE
        if incomparable_reasons
        else Comparability.PARTIALLY_COMPARABLE
        if reasons
        else Comparability.COMPARABLE
    )

    before_findings = _findings_by_fingerprint(before)
    after_findings = _findings_by_fingerprint(after)
    before_keys = set(before_findings)
    after_keys = set(after_findings)
    added = tuple(after_findings[key] for key in sorted(after_keys - before_keys))
    resolved = tuple(before_findings[key] for key in sorted(before_keys - after_keys))
    unchanged = tuple(after_findings[key] for key in sorted(before_keys & after_keys))
    changed = _changed_groups(resolved, added)

    before_limits = _limitations(before)
    after_limits = _limitations(after)
    before_files = _source_files(before)
    after_files = _source_files(after)
    return ReportComparison(
        status=status,
        reasons=reasons,
        added=added,
        resolved=resolved,
        unchanged=unchanged,
        changed=changed,
        new_limitations=tuple(
            after_limits[key] for key in sorted(set(after_limits) - set(before_limits))
        ),
        resolved_limitations=tuple(
            before_limits[key] for key in sorted(set(before_limits) - set(after_limits))
        ),
        added_source_files=tuple(sorted(after_files - before_files)),
        removed_source_files=tuple(sorted(before_files - after_files)),
    )


def render_comparison_json(comparison: ReportComparison) -> str:
    return render_json_artifact(comparison.to_dict())


def render_comparison_text(comparison: ReportComparison) -> str:
    lines = [
        f"Deadtrace report comparison ({comparison.status.value})",
        (
            f"Added: {len(comparison.added)} | Resolved: {len(comparison.resolved)} | "
            f"Unchanged: {len(comparison.unchanged)} | Changed groups: {len(comparison.changed)}"
        ),
        (
            f"New limitations: {len(comparison.new_limitations)} | "
            f"Resolved limitations: {len(comparison.resolved_limitations)}"
        ),
        (
            f"Source files added: {len(comparison.added_source_files)} | "
            f"removed: {len(comparison.removed_source_files)}"
        ),
    ]
    lines.extend(f"Method change: {reason}" for reason in comparison.reasons)
    for label, findings in (("NEW", comparison.added), ("RESOLVED", comparison.resolved)):
        for finding in findings:
            lines.append(
                f"{label} {finding.get('code', '?')} {finding.get('fingerprint', '?')} "
                f"{finding.get('title', '')}"
            )
    return "\n".join(lines) + "\n"


def _method_change_reasons(before: dict[str, Any], after: dict[str, Any]) -> tuple[str, ...]:
    labels = {
        "schema_version": "report schema changed",
        "tool_version": "analyzer version changed",
        "model_revision": "model revision changed",
        "config_digest": "configuration changed",
        "target_environment_digest": "target dependency versions changed",
        "worlds": "world roots or retained contracts changed",
        "capabilities": "capability set changed",
        "analysis_state": "analysis completeness changed",
        "input_issues": "input issues changed",
    }
    return tuple(labels[key] for key in labels if before.get(key) != after.get(key))


def _world_ids(method: dict[str, Any]) -> set[tuple[object, object]]:
    worlds = method.get("worlds", [])
    if not isinstance(worlds, list):
        return set()
    return {
        (world_id.get("profile"), world_id.get("scenario"))
        for world in worlds
        if isinstance(world, dict) and isinstance((world_id := world.get("id")), dict)
    }


def _source_files(payload: dict[str, Any]) -> set[str]:
    source_universe = payload.get("source_universe")
    if not isinstance(source_universe, dict):
        return set()
    files = source_universe.get("files", [])
    if not isinstance(files, list):
        return set()
    return {path for path in files if isinstance(path, str)}


def _findings_by_fingerprint(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    findings = payload["findings"]
    assert isinstance(findings, list)
    return {
        finding["fingerprint"]: finding
        for finding in findings
        if isinstance(finding, dict) and isinstance(finding.get("fingerprint"), str)
    }


def _member_identities(finding: dict[str, Any]) -> set[tuple[object, ...]]:
    members = finding.get("members", [])
    if not isinstance(members, list):
        return set()
    return {
        (
            member.get("path"),
            member.get("qualified_name"),
            member.get("kind"),
            member.get("occurrence"),
        )
        for member in members
        if isinstance(member, dict)
    }


def _changed_groups(
    resolved: tuple[dict[str, Any], ...], added: tuple[dict[str, Any], ...]
) -> tuple[dict[str, str], ...]:
    changes: list[dict[str, str]] = []
    for old in resolved:
        old_members = _member_identities(old)
        matches = [
            new
            for new in added
            if new.get("code") == old.get("code")
            and old_members.intersection(_member_identities(new))
        ]
        if len(matches) == 1:
            changes.append(
                {
                    "before": str(old["fingerprint"]),
                    "after": str(matches[0]["fingerprint"]),
                }
            )
    return tuple(sorted(changes, key=lambda item: (item["before"], item["after"])))


def _limitations(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    worlds = payload["worlds"]
    assert isinstance(worlds, list)
    for world in worlds:
        if not isinstance(world, dict):
            continue
        world_id = world.get("id")
        limitations = world.get("limitations", [])
        if not isinstance(limitations, list):
            continue
        for limitation in limitations:
            if not isinstance(limitation, dict):
                continue
            key = repr(
                (
                    world_id,
                    limitation.get("code"),
                    limitation.get("message"),
                    limitation.get("origin"),
                )
            )
            result[key] = {"world": world_id, **limitation}
    return result
