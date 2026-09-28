"""Baseline existing review findings without changing semantic analysis."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from deadtrace.artifacts import ArtifactError, render_json_artifact
from deadtrace.comparison import (
    method_change_reasons,
    method_descriptor,
    validate_semantic_report,
)


@dataclass(frozen=True, slots=True)
class BaselineApplication:
    payload: dict[str, Any]
    comparable: bool
    accepted: int
    new: int
    stale: int
    reasons: tuple[str, ...] = ()


def create_baseline(report: dict[str, Any], reason: str) -> dict[str, Any]:
    """Create an explicit debt ledger from one reviewed semantic report."""

    validate_semantic_report(report)
    if not reason.strip():
        raise ArtifactError("baseline reason must not be empty")
    findings = report["findings"]
    assert isinstance(findings, list)
    return {
        "schema_version": 1,
        "kind": "deadtrace-baseline",
        "method": method_descriptor(report),
        "source_digest": report["descriptor"].get("source_digest"),
        "entries": [
            {
                "fingerprint": finding["fingerprint"],
                "code": finding.get("code"),
                "members": finding.get("members", []),
                "reason": reason,
            }
            for finding in findings
            if isinstance(finding, dict)
        ],
    }


def update_baseline(
    baseline: dict[str, Any],
    report: dict[str, Any],
    *,
    accept_new: bool = False,
    reason: str | None = None,
) -> dict[str, Any]:
    """Rebase reviewed entries; accepting new findings always requires an explicit reason.

    An entry carries over to a finding with its fingerprint, or with its code and exactly its
    members when a method change renewed the fingerprint.
    """

    validate_baseline(baseline)
    validate_semantic_report(report)
    if accept_new and (reason is None or not reason.strip()):
        raise ArtifactError("accepting new baseline findings requires a non-empty reason")
    old_entries = baseline["entries"]
    findings = report["findings"]
    assert isinstance(old_entries, list)
    assert isinstance(findings, list)
    by_fingerprint = {
        entry["fingerprint"]: entry for entry in old_entries if isinstance(entry, dict)
    }
    by_content = {_content_key(entry): entry for entry in old_entries if isinstance(entry, dict)}
    entries: list[dict[str, Any]] = []
    for finding in findings:
        assert isinstance(finding, dict)
        fingerprint = finding["fingerprint"]
        old = by_fingerprint.get(fingerprint) or by_content.get(_content_key(finding))
        if old is not None:
            entries.append(
                {
                    **deepcopy(old),
                    "fingerprint": fingerprint,
                    "members": deepcopy(finding.get("members", [])),
                }
            )
        elif accept_new:
            entries.append(
                {
                    "fingerprint": fingerprint,
                    "code": finding.get("code"),
                    "members": finding.get("members", []),
                    "reason": reason,
                }
            )
    return {
        "schema_version": 1,
        "kind": "deadtrace-baseline",
        "method": method_descriptor(report),
        "source_digest": report["descriptor"].get("source_digest"),
        "entries": entries,
    }


def validate_baseline(payload: dict[str, Any]) -> None:
    if payload.get("schema_version") != 1 or payload.get("kind") != "deadtrace-baseline":
        raise ArtifactError("baseline must use deadtrace-baseline schema 1")
    if not isinstance(payload.get("method"), dict):
        raise ArtifactError("baseline method must be an object")
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise ArtifactError("baseline entries must be an array")
    fingerprints: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("fingerprint"), str):
            raise ArtifactError("every baseline entry must have a string fingerprint")
        fingerprint = entry["fingerprint"]
        if fingerprint in fingerprints:
            raise ArtifactError(f"duplicate baseline fingerprint: {fingerprint}")
        fingerprints.add(fingerprint)


def apply_baseline(report: dict[str, Any], baseline: dict[str, Any]) -> BaselineApplication:
    """Annotate a report; never remove findings or limitations."""

    validate_semantic_report(report)
    validate_baseline(baseline)
    reasons = method_change_reasons(baseline["method"], method_descriptor(report))
    comparable = not reasons
    entries = baseline["entries"]
    assert isinstance(entries, list)
    baseline_fingerprints = {entry["fingerprint"] for entry in entries if isinstance(entry, dict)}
    projected = deepcopy(report)
    findings = projected["findings"]
    assert isinstance(findings, list)
    current = {
        finding["fingerprint"]
        for finding in findings
        if isinstance(finding, dict) and isinstance(finding.get("fingerprint"), str)
    }
    accepted = current.intersection(baseline_fingerprints) if comparable else set()
    for finding in findings:
        assert isinstance(finding, dict)
        finding["baseline_status"] = "accepted" if finding["fingerprint"] in accepted else "new"
    stale = baseline_fingerprints - current
    summary = projected.get("summary")
    if not isinstance(summary, dict):
        summary = {}
        projected["summary"] = summary
    summary.update(
        {
            "baselined_finding_count": len(accepted),
            "new_finding_count": len(current - accepted),
            "stale_baseline_count": len(stale),
        }
    )
    projected["baseline"] = {
        "status": "comparable" if comparable else "incomparable",
        "reasons": list(reasons),
        "source_digest": baseline.get("source_digest"),
        "stale_fingerprints": sorted(stale),
    }
    return BaselineApplication(
        payload=projected,
        comparable=comparable,
        accepted=len(accepted),
        new=len(current - accepted),
        stale=len(stale),
        reasons=reasons,
    )


def _content_key(item: dict[str, Any]) -> tuple[object, ...]:
    """A finding's code and member identities, the content its fingerprint hashes."""

    members = item.get("members", [])
    return (
        item.get("code"),
        tuple(
            sorted(
                (
                    str(member.get("path")),
                    str(member.get("qualified_name")),
                    str(member.get("kind")),
                    str(member.get("occurrence")),
                )
                for member in (members if isinstance(members, list) else [])
                if isinstance(member, dict)
            )
        ),
    )


def render_baseline_json(payload: dict[str, Any]) -> str:
    return render_json_artifact(payload)
