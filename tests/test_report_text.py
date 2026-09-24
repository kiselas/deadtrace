"""Text reports count identical limitations once and summarize many conservative guards."""

from __future__ import annotations

from deadtrace.core import Limitation
from deadtrace.semantic_report import limitation_lines


def _guard(message: str) -> Limitation:
    return Limitation(code="DT2002", message=message)


def test_identical_limitations_are_counted_and_other_codes_always_listed() -> None:
    limitations = [
        Limitation(code="DT3001", message="configured root cannot be resolved: a"),
        _guard("registered by decorator app.task"),
        _guard("registered by decorator app.task"),
        Limitation(code="DT3001", message="configured root cannot be resolved: a"),
    ]

    assert limitation_lines(limitations, indent="  ", label="limitation ") == [
        "  limitation DT3001: configured root cannot be resolved: a (x2)",
        "  limitation DT2002: registered by decorator app.task (x2)",
    ]


def test_many_kinds_of_guard_collapse_into_a_summary() -> None:
    limitations = [
        Limitation(code="DT4001", message="version mismatch"),
        *(_guard(f"guard {index}") for index in range(8)),
        *(_guard("common guard") for _ in range(3)),
        *(_guard("frequent guard") for _ in range(2)),
    ]

    assert limitation_lines(limitations, indent="", label="") == [
        "DT4001: version mismatch",
        "DT2002: 13 conservative guards of 10 kinds protect code that may run; the most common:",
        "    common guard (x3)",
        "    frequent guard (x2)",
        "    guard 0",
        "    and 7 more kinds; the JSON report lists every guard",
    ]


def test_few_kinds_of_guard_are_listed_by_count() -> None:
    limitations = [_guard("b"), _guard("a"), _guard("b")]

    assert limitation_lines(limitations, indent="", label="") == ["DT2002: b (x2)", "DT2002: a"]
