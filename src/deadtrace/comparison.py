"""Compare two saved semantic reports without re-running analysis."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from deadtrace.artifacts import ArtifactError, render_json_artifact
from deadtrace.target_environment import UNTESTED_VERSION

CAUSE_ORDER = (
    "incomplete",
    "method_changed",
    "unattributed",
    "blocked",
    "regrouped",
    "unexplained",
    "protected",
    "kept",
    "reached",
    "deleted",
)
"""Why a finding is no longer reported (ADR-0122), from the weakest evidence that its code is gone
or used to the strongest. A finding takes the weakest cause among its members, so one member under
an unknown boundary keeps the whole finding from reading as resolved by a consumer."""


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
    added_worlds: tuple[str, ...] = ()
    removed_worlds: tuple[str, ...] = ()
    added_roots: tuple[str, ...] = ()
    removed_roots: tuple[str, ...] = ()

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
            "worlds": {
                "added": list(self.added_worlds),
                "removed": list(self.removed_worlds),
                "added_roots": list(self.added_roots),
                "removed_roots": list(self.removed_roots),
            },
            "summary": {
                "added_findings": len(self.added),
                "resolved_findings": len(self.resolved),
                "resolved_by_cause": cause_counts(
                    finding.get("resolution", {}) for finding in self.resolved
                ),
                "unchanged_findings": len(self.unchanged),
                "changed_groups": len(self.changed),
                "new_limitations": len(self.new_limitations),
                "resolved_limitations": len(self.resolved_limitations),
                "added_source_files": len(self.added_source_files),
                "removed_source_files": len(self.removed_source_files),
                "added_worlds": len(self.added_worlds),
                "removed_worlds": len(self.removed_worlds),
                "added_roots": len(self.added_roots),
                "removed_roots": len(self.removed_roots),
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
    """Return the analysis-method fields that determine report comparability.

    Worlds, their roots, and the versions of dependencies the model does not interpret follow
    from the source under the same method, so they are source changes (ADR-0021).
    """

    validate_semantic_report(payload)
    descriptor = payload["descriptor"]
    assert isinstance(descriptor, dict)
    capabilities = payload["capabilities"]
    assert isinstance(capabilities, list)
    return {
        "schema_version": payload["schema_version"],
        "model_revision": descriptor.get("model_revision"),
        "config_digest": descriptor.get("config_digest"),
        "target_environment": _weakening_target_issues(payload),
        "analysis_state": payload.get("analysis_state"),
        "input_issues": sorted(
            [str(issue.get("code")), str(issue.get("path"))]
            for issue in payload.get("issues", [])
            if isinstance(issue, dict)
        ),
        "capabilities": capabilities,
    }


def method_change_reasons(before: dict[str, Any], after: dict[str, Any]) -> tuple[str, ...]:
    """Name the method fields that differ between two method descriptors."""

    return tuple(
        label for key, label in _METHOD_LABELS.items() if before.get(key) != after.get(key)
    )


_METHOD_LABELS = {
    "schema_version": "report schema changed",
    "model_revision": "model revision changed",
    "config_digest": "configuration changed",
    "target_environment": "support of target dependency versions changed",
    "capabilities": "capability set changed",
    "analysis_state": "analysis completeness changed",
    "input_issues": "input issues changed",
}


def _weakening_target_issues(payload: dict[str, Any]) -> list[list[str]]:
    """Dependency versions matter to the method only where they weaken the model."""

    environment = payload.get("target_environment")
    issues = environment.get("issues", []) if isinstance(environment, dict) else []
    return sorted(
        [str(issue.get("package")), str(issue.get("code"))]
        for issue in issues
        if isinstance(issue, dict) and issue.get("code") != UNTESTED_VERSION
    )


def compare_reports(before: dict[str, Any], after: dict[str, Any]) -> ReportComparison:
    """Compare reports while keeping method changes separate from source changes."""

    before_method = method_descriptor(before)
    after_method = method_descriptor(after)
    method_reasons = list(method_change_reasons(before_method, after_method))
    incomplete = (
        before_method["analysis_state"] != "complete"
        or after_method["analysis_state"] != "complete"
    )
    if incomplete:
        method_reasons.append("one or both analyses are incomplete")
    before_roots = _world_roots(before)
    after_roots = _world_roots(after)
    incomparable_reasons: list[str] = []
    if not set(before_roots).intersection(after_roots):
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
    resolved = _with_resolutions(
        before,
        after,
        tuple(before_findings[key] for key in sorted(before_keys - after_keys)),
        reasons=reasons,
    )
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
        added_worlds=tuple(sorted(set(after_roots) - set(before_roots))),
        removed_worlds=tuple(sorted(set(before_roots) - set(after_roots))),
        added_roots=_root_delta(after_roots, before_roots),
        removed_roots=_root_delta(before_roots, after_roots),
    )


ResolvedExplainer = Callable[[list[dict[str, Any]]], list[dict[str, Any]]]
"""Given earlier findings the analysis no longer shows, the cause of each (ADR-0122)."""


def apply_previous(
    report: dict[str, Any], previous: dict[str, Any], *, explain: ResolvedExplainer
) -> dict[str, Any]:
    """Annotate a report with what changed since an earlier report of the same project.

    The earlier report is not a reviewed baseline: nothing is accepted and no exit code depends
    on it. The annotation names the comparability, the new findings, and the cause of each
    finding no longer shown, so an agent that scans again after an edit can say why a finding
    disappeared rather than only that the count fell.
    """

    validate_semantic_report(previous)
    comparison = compare_reports(previous, report)
    projected = deepcopy(report)
    resolved = explain(
        [
            {key: finding.get(key) for key in ("fingerprint", "code", "members")}
            for finding in comparison.resolved
        ]
    )
    projected["previous"] = {
        "comparability": comparison.status.value,
        "reasons": list(comparison.reasons),
        "source_digest": previous["descriptor"].get("source_digest"),
        "new_fingerprints": [str(finding["fingerprint"]) for finding in comparison.added],
        "resolved": resolved,
        "resolved_by_cause": cause_counts(resolved),
    }
    return projected


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
        (
            f"Worlds added: {len(comparison.added_worlds)} | "
            f"removed: {len(comparison.removed_worlds)} | "
            f"roots added: {len(comparison.added_roots)} | "
            f"removed: {len(comparison.removed_roots)}"
        ),
    ]
    lines.extend(f"Method change: {reason}" for reason in comparison.reasons)
    by_cause = cause_counts(finding.get("resolution", {}) for finding in comparison.resolved)
    if by_cause:
        lines.append(
            "Resolved by cause: "
            + ", ".join(f"{cause} {count}" for cause, count in by_cause.items())
        )
    for finding in comparison.added:
        lines.append(
            f"NEW {finding.get('code', '?')} {finding.get('fingerprint', '?')} "
            f"{finding.get('title', '')}"
        )
    for finding in comparison.resolved:
        lines.append(
            f"RESOLVED {finding.get('code', '?')} {finding.get('fingerprint', '?')} "
            f"{finding.get('title', '')}"
        )
        if isinstance(resolution := finding.get("resolution"), Mapping):
            lines.append(f"  {describe_resolution(resolution)}")
    return "\n".join(lines) + "\n"


def cause_counts(resolutions: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    """How many resolved findings each cause accounts for, weakest evidence first."""

    counts: dict[str, int] = {}
    for resolution in resolutions:
        if isinstance(cause := resolution.get("cause"), str):
            counts[cause] = counts.get(cause, 0) + 1
    return {cause: counts[cause] for cause in sorted(counts, key=cause_rank)}


def cause_rank(cause: str) -> int:
    return CAUSE_ORDER.index(cause) if cause in CAUSE_ORDER else len(CAUSE_ORDER)


def describe_resolution(resolution: Mapping[str, Any]) -> str:
    """One line on why a finding is no longer reported, for a person or an agent to repeat."""

    cause = str(resolution.get("cause", "unattributed"))
    members = resolution.get("members")
    member = next(
        (
            item
            for item in (members if isinstance(members, list) else [])
            if isinstance(item, Mapping) and item.get("status") == cause
        ),
        None,
    )
    found = member.get("evidence", {}) if member is not None else {}
    evidence: Mapping[str, Any] = found if isinstance(found, Mapping) else {}
    subject = f"{member.get('qualified_name')}: " if member is not None else ""
    if cause == "deleted":
        return f"deleted: {subject}the code is no longer in the source"
    if cause == "reached":
        world = evidence.get("world", "?")
        if "root" in evidence:
            return f"reached: {subject}now a root of {world} ({evidence.get('root')})"
        return (
            f"reached: {subject}{evidence.get('edge', 'edge')} from "
            f"{_where(evidence.get('from'))} in {world}"
        )
    if cause == "protected":
        boundary = evidence.get("boundary", {})
        notes = []
        if evidence.get("sole") is True:
            notes.append("the finding returns without it")
        elif evidence.get("sole") is False:
            notes.append("other boundaries protect it too")
        if evidence.get("new_boundary") is True:
            notes.append("new boundary")
        elif evidence.get("new_boundary") is False:
            notes.append("boundary existed before")
        suffix = f" ({'; '.join(notes)})" if notes else ""
        through = (
            f"{boundary.get('reason', '?')} at {_where(boundary)} in {evidence.get('world', '?')}"
        )
        if "from" in evidence:
            return (
                f"protected: {subject}{evidence.get('edge', 'edge')} from "
                f"{_where(evidence['from'])}, which itself may run only through {through}{suffix}"
            )
        return (
            f"protected: {subject}no resolved path reaches it; it may run only through "
            f"{through}{suffix}"
        )
    if cause == "kept":
        return f"kept: {subject}{evidence.get('contract', 'retained')}"
    if cause == "regrouped":
        target = evidence or resolution
        blocked = target.get("blocked")
        held = f", held back: {', '.join(blocked)}" if isinstance(blocked, list) else ""
        return (
            f"regrouped: {subject}now part of {target.get('code', '?')} "
            f"{target.get('fingerprint', '?')}{held}"
        )
    if cause == "blocked":
        blocked = resolution.get("blocked") or ["a blocking rule"]
        return f"blocked: held back by {', '.join(blocked)}; the code is unchanged in the graph"
    if cause == "incomplete":
        return "incomplete: the later analysis is incomplete and cannot vouch for absent findings"
    if cause == "method_changed":
        return f"method changed: {'; '.join(resolution.get('reasons', [])) or 'unknown'}"
    if cause == "unexplained":
        return f"unexplained: {subject}unreached, but no longer reported for another reason"
    return (
        "unattributed: the later report records no cause; scan with --baseline made from the "
        "earlier report to attribute it"
    )


def _where(place: object) -> str:
    if not isinstance(place, Mapping):
        return "?"
    name = str(place.get("name", "?"))
    return f"{name} ({place.get('path')}:{place.get('line')})" if place.get("path") else name


def _world_roots(payload: dict[str, Any]) -> dict[str, frozenset[str]]:
    worlds = payload.get("worlds", [])
    if not isinstance(worlds, list):
        return {}
    result: dict[str, frozenset[str]] = {}
    for world in worlds:
        if not isinstance(world, dict) or not isinstance((world_id := world.get("id")), dict):
            continue
        roots = world.get("roots", [])
        result[f"{world_id.get('profile')}:{world_id.get('scenario')}"] = (
            frozenset(root for root in roots if isinstance(root, str))
            if isinstance(roots, list)
            else frozenset()
        )
    return result


def _root_delta(
    these: dict[str, frozenset[str]], others: dict[str, frozenset[str]]
) -> tuple[str, ...]:
    """Roots of common worlds present in ``these`` only; new worlds are listed as worlds."""

    return tuple(
        sorted(
            f"{world}: {root}"
            for world, roots in these.items()
            if world in others
            for root in roots - others[world]
        )
    )


def _source_files(payload: dict[str, Any]) -> set[str]:
    source_universe = payload.get("source_universe")
    if not isinstance(source_universe, dict):
        return set()
    files = source_universe.get("files", [])
    if not isinstance(files, list):
        return set()
    return {path for path in files if isinstance(path, str)}


def _findings_by_fingerprint(
    payload: dict[str, Any], key: str = "findings"
) -> dict[str, dict[str, Any]]:
    findings = payload.get(key, [])
    if not isinstance(findings, list):
        return {}
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


def _with_resolutions(
    before: dict[str, Any],
    after: dict[str, Any],
    resolved: tuple[dict[str, Any], ...],
    *,
    reasons: tuple[str, ...],
) -> tuple[dict[str, Any], ...]:
    """Resolved findings with the cause of each (ADR-0122).

    The later scan records causes from its graph when it was given the earlier report
    (``--previous``) or a baseline. Otherwise only what the two reports show is used: a finding now
    held back, members now in another finding, or their source files removed. Anything else stays
    ``unattributed`` rather than read as gone.
    """

    recorded = recorded_causes(after)
    later_blocked = _findings_by_fingerprint(after, "blocked_findings")
    owner: dict[tuple[object, ...], dict[str, Any]] = {}
    for finding in (*_findings_by_fingerprint(after).values(), *later_blocked.values()):
        for identity in _member_identities(finding):
            owner.setdefault(identity, finding)
    later_files = _source_files(after)
    guards = _guard_origins(before)
    result: list[dict[str, Any]] = []
    for finding in resolved:
        fingerprint = finding["fingerprint"]
        identities = sorted(_member_identities(finding), key=repr)
        later = next((owner[item] for item in identities if item in owner), None)
        resolution: dict[str, Any]
        if fingerprint in recorded:
            resolution = {
                key: value
                for key, value in deepcopy(recorded[fingerprint]).items()
                if key not in {"fingerprint", "code"}
            }
            _mark_new_boundaries(resolution, guards)
        elif fingerprint in later_blocked:
            resolution = {
                "cause": "blocked",
                "blocked": list(later_blocked[fingerprint].get("blocked", [])),
            }
        elif later is not None:
            resolution = {
                "cause": "regrouped",
                "fingerprint": later.get("fingerprint"),
                "code": later.get("code"),
            }
            if later.get("blocked"):
                resolution["blocked"] = list(later["blocked"])
        elif identities and all(identity[0] not in later_files for identity in identities):
            resolution = {"cause": "deleted"}
        elif reasons:
            resolution = {"cause": "method_changed", "reasons": list(reasons)}
        else:
            resolution = {"cause": "unattributed"}
        result.append({**finding, "resolution": resolution})
    return tuple(result)


def recorded_causes(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """The causes a scan recorded for earlier findings it no longer shows, by fingerprint, from
    its baseline annotation or its ``previous`` section (ADR-0122)."""

    recorded: dict[str, dict[str, Any]] = {}
    for section, key in (("baseline", "stale_entries"), ("previous", "resolved")):
        annotation = report.get(section)
        entries = annotation.get(key, []) if isinstance(annotation, dict) else []
        for entry in entries if isinstance(entries, list) else []:
            if isinstance(entry, dict) and isinstance(entry.get("fingerprint"), str):
                recorded.setdefault(entry["fingerprint"], entry)
    return recorded


def _guard_origins(payload: dict[str, Any]) -> dict[tuple[str, str], set[str] | None]:
    """Guard messages of each world with the origins the report names, or None where it groups
    guards by message (ADR-0079)."""

    result: dict[tuple[str, str], set[str] | None] = {}
    for entry in _limitations(payload).values():
        world = entry.get("world")
        if entry.get("code") == "DT2002" and isinstance(world, dict):
            result[(f"{world.get('profile')}:{world.get('scenario')}", str(entry["message"]))] = (
                set()
            )
    for world in payload.get("worlds", []):
        if not isinstance(world, dict) or not isinstance(world_id := world.get("id"), dict):
            continue
        world_key = f"{world_id.get('profile')}:{world_id.get('scenario')}"
        for limitation in world.get("limitations", []):
            if not isinstance(limitation, dict) or limitation.get("code") != "DT2002":
                continue
            key = (world_key, str(limitation.get("message")))
            origins = result.get(key)
            if limitation.get("origin") is None or origins is None:
                result[key] = None
            else:
                origins.add(str(limitation["origin"]))
    return result


def _mark_new_boundaries(
    resolution: dict[str, Any], guards: Mapping[tuple[str, str], set[str] | None]
) -> None:
    """Whether each protected member's boundary was already a guard in the earlier report; null
    when that report lists the guard's message but groups its origins."""

    members = resolution.get("members", [])
    for member in members if isinstance(members, list) else []:
        if not isinstance(member, dict) or member.get("status") != "protected":
            continue
        evidence = member["evidence"]
        boundary = evidence["boundary"]
        key = (str(evidence.get("world")), str(boundary.get("reason")))
        if key not in guards:
            evidence["new_boundary"] = True
        elif (origins := guards[key]) is None:
            evidence["new_boundary"] = None
        else:
            evidence["new_boundary"] = boundary.get("name") not in origins


def _limitations(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    worlds = payload["worlds"]
    assert isinstance(worlds, list)
    # Limitations every world has are listed once (ADR-0079); expand them so that reports written
    # before and after that change compare alike.
    shared = payload.get("shared_limitations", [])
    shared = shared if isinstance(shared, list) else []
    for world in worlds:
        if not isinstance(world, dict):
            continue
        world_id = world.get("id")
        limitations = world.get("limitations", [])
        if not isinstance(limitations, list):
            continue
        limitations = [*limitations, *shared]
        for limitation in limitations:
            if not isinstance(limitation, dict):
                continue
            # Guards are compared by message: reports group their origins by default (ADR-0079).
            guard = limitation.get("code") == "DT2002"
            key = repr(
                (
                    world_id,
                    limitation.get("code"),
                    limitation.get("message"),
                    None if guard else limitation.get("origin"),
                )
            )
            entry = {"world": world_id, **limitation}
            if guard:
                entry = {"world": world_id, "code": "DT2002", "message": limitation.get("message")}
            result[key] = entry
    return result
