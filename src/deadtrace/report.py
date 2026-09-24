"""Stable text and JSON boundaries for inventory-only output."""

from __future__ import annotations

import json
from typing import Any

from deadtrace import __version__
from deadtrace.model import InventoryReport

REPORT_SCHEMA_VERSION = 0


def report_dict(report: InventoryReport) -> dict[str, Any]:
    """Convert the internal snapshot to experimental report schema 0."""

    visible = tuple(item for item in report.definitions if not item.report_excluded)
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "analysis_state": "inventory_only",
        "validation": "not_performed",
        "tool": {"name": "deadtrace", "version": __version__},
        "source_universe": {"root": report.root, "files": list(report.files)},
        "inventory": {
            "definitions": [item.to_dict() for item in report.definitions],
            "visible_definition_count": len(visible),
        },
        "issues": [issue.to_dict() for issue in report.issues],
        "findings": [],
        "summary": {
            "file_count": len(report.files),
            "definition_count": len(report.definitions),
            "issue_count": len(report.issues),
        },
    }


def render_json(report: InventoryReport) -> str:
    return json.dumps(report_dict(report), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def render_text(report: InventoryReport) -> str:
    lines = [
        "Deadtrace inventory (analysis_state=inventory_only)",
        f"Root: {report.root}",
        (
            f"Files: {len(report.files)} | Definitions: {len(report.definitions)} "
            f"| Issues: {len(report.issues)}"
        ),
        "",
    ]
    for definition in report.definitions:
        if definition.report_excluded:
            continue
        location = f"{definition.path}:{definition.span.start_line}:{definition.span.start_column}"
        lines.append(
            f"{location}  {definition.kind.value:<8}  {definition.qualified_name}"
            f"  occurrence={definition.occurrence}"
        )
    if not any(not item.report_excluded for item in report.definitions):
        lines.append("No visible definitions found.")
    lines.extend(
        [
            "",
            "No dead-code analysis has been performed; findings are intentionally empty.",
        ]
    )
    return "\n".join(lines) + "\n"
