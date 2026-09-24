from __future__ import annotations

import json

from deadtrace.model import Definition, DefinitionKind, InventoryReport, SourceSpan
from deadtrace.report import render_json, render_text


def _report() -> InventoryReport:
    return InventoryReport(
        root="/project",
        files=("app.py",),
        definitions=(
            Definition(
                path="app.py",
                qualified_name="endpoint",
                name="endpoint",
                kind=DefinitionKind.FUNCTION,
                owner=None,
                occurrence=0,
                span=SourceSpan(1, 0, 2, 8),
                report_excluded=False,
            ),
        ),
        issues=(),
    )


def test_json_schema_is_explicitly_inventory_only() -> None:
    payload = json.loads(render_json(_report()))

    assert payload["schema_version"] == 0
    assert payload["analysis_state"] == "inventory_only"
    assert payload["validation"] == "not_performed"
    assert payload["findings"] == []


def test_text_does_not_claim_dead_code_analysis() -> None:
    output = render_text(_report())

    assert "inventory_only" in output
    assert "No dead-code analysis has been performed" in output


def test_text_handles_fully_excluded_inventory() -> None:
    original = _report().definitions[0]
    excluded = Definition(
        path=original.path,
        qualified_name=original.qualified_name,
        name=original.name,
        kind=original.kind,
        owner=original.owner,
        occurrence=original.occurrence,
        span=original.span,
        report_excluded=True,
    )
    report = InventoryReport("/project", ("app.py",), (excluded,), ())

    assert "No visible definitions found" in render_text(report)
