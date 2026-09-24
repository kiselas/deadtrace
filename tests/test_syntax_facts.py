"""Syntax facts read from stdlib ``ast`` trees keep the meaning the analysis relies on.

See ADR-0007: each case below is a place where the ``ast`` shape differs from the facts the
analysis consumes, and the helpers restore those facts.
"""

from __future__ import annotations

import ast
import warnings
from pathlib import Path

import pytest

from deadtrace.inventory import SourceText, inventory_source, parse_source
from deadtrace.python_frontend import (
    PythonModule,
    _dotted_name,
    build_python_program,
    call_arguments,
    simple_block_statements,
    single_string_literal,
    subscript_items,
)
from deadtrace.scanner import SourceCollection, SourceUnit


def _expression(source: str) -> tuple[ast.expr, SourceText]:
    parsed = parse_source(source)
    statement = parsed.tree.body[0]
    assert isinstance(statement, ast.Expr)
    return statement.value, parsed.text


def _module(source: str) -> PythonModule:
    collection = SourceCollection(
        root=Path("/project"),
        files=("main.py",),
        units=(SourceUnit("main.py", Path("/project/main.py"), source, "digest"),),
        issues=(),
    )
    return build_python_program(collection).modules["main"]


@pytest.mark.parametrize(
    ("source", "items"),
    [
        ("x[a]", ["Name"]),
        ("x[a, b]", ["Name", "Name"]),
        ("x[a,]", ["Name"]),
        ("x[(a, b)]", ["Tuple"]),
        ("x[ (a, b) ]", ["Tuple"]),
        ("x[(a), b]", ["Name", "Name"]),
        ("x[(a), (b)]", ["Name", "Name"]),
        ("x[(a,)]", ["Tuple"]),
        ("x[()]", ["Tuple"]),
        ("x[a:b, c]", ["Slice", "Name"]),
        ("x[\n    (a, b)\n]", ["Tuple"]),
    ],
)
def test_subscript_items_follow_the_written_index_items(source: str, items: list[str]) -> None:
    expression, text = _expression(source)
    assert isinstance(expression, ast.Subscript)

    assert [type(item).__name__ for item in subscript_items(expression, text)] == items


def test_call_arguments_are_listed_in_source_order_with_their_kind() -> None:
    expression, _ = _expression("f(a, key=1, *rest, **options)")
    assert isinstance(expression, ast.Call)

    assert [
        (_dotted_name(argument.value) or "1", argument.keyword, argument.star)
        for argument in call_arguments(expression)
    ] == [("a", None, ""), ("1", "key", ""), ("rest", None, "*"), ("options", None, "**")]


@pytest.mark.parametrize(
    ("source", "value"),
    [
        ('"name"', "name"),
        ("'name'", "name"),
        ('r"na\\me"', "na\\me"),
        ('"na" "me"', None),
        ('(\n    "na"\n    "me"\n)', None),
        ('f"name"', None),
        ('b"name"', None),
        ("name", None),
    ],
)
def test_single_string_literal_accepts_exactly_one_plain_string(
    source: str, value: str | None
) -> None:
    expression, text = _expression(source)

    assert single_string_literal(expression, text) == value


def test_bodies_on_the_header_line_have_no_block_statements() -> None:
    module = _module(
        "class Inline: value = compute()\n"
        "\n"
        "class Block:\n"
        "    value = compute(); other = 1\n"
        "    if other:\n"
        "        pass\n"
    )
    inline, block = (
        statement for statement in module.tree.body if isinstance(statement, ast.ClassDef)
    )

    assert simple_block_statements(module, inline) == ()
    assert [type(statement).__name__ for statement in simple_block_statements(module, block)] == [
        "Assign",
        "Assign",
    ]


def test_inventory_columns_count_characters_not_utf8_bytes() -> None:
    source = 'x = "ё"; y = "й"\nclass Ёлка:\n    def ёж(self) -> str: return "日本"\n'

    definitions = inventory_source(source, path="main.py")

    assert [
        (item.qualified_name, item.span.start_column, item.span.end_line, item.span.end_column)
        for item in definitions
    ] == [("Ёлка", 0, 3, 36), ("Ёлка.ёж", 4, 3, 36)]


def test_source_text_columns_and_segments_use_characters_on_non_ascii_lines() -> None:
    text = SourceText('a = "ё"\r\nb = f(ё, "日本")\n')
    call = parse_source(text.text).tree.body[1]
    assert isinstance(call, ast.Assign)

    assert text.line(2) == 'b = f(ё, "日本")'
    assert text.column(2, call.value.end_col_offset or 0) == 14
    assert text.segment(call.value) == 'f(ё, "日本")'


def test_parse_warnings_of_the_target_program_are_not_emitted() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        parsed = parse_source('pattern = "\\d+"\n')

    assert isinstance(parsed.tree.body[0], ast.Assign)


def test_syntax_errors_are_reported_as_stdlib_syntax_errors() -> None:
    with pytest.raises(SyntaxError):
        parse_source("def broken(:\n")


@pytest.mark.parametrize(("source", "name"), [("None", "None"), ("True", "True"), ("x.y", "x.y")])
def test_name_constants_are_dotted_names(source: str, name: str) -> None:
    expression, _ = _expression(source)

    assert _dotted_name(expression) == name


def test_numbers_and_strings_are_not_dotted_names() -> None:
    for source in ("1", '"x"', "f()"):
        expression, _ = _expression(source)
        assert _dotted_name(expression) is None
