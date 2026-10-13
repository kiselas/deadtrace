"""Nested import discovery needs statements, not their expression payloads."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

import pytest

from deadtrace.python_frontend import PythonModule, _nested_module_imports, build_python_program
from deadtrace.scanner import SourceCollection, SourceUnit


def _modules(source: str) -> dict[str, PythonModule]:
    sources = {
        "backends/__init__.py": "",
        "backends/alpha.py": "",
        "backends/beta.py": "",
        "backends/gamma.py": "",
        "backends/delta.py": "",
        "main.py": source,
    }
    collection = SourceCollection(
        root=Path("/project"),
        files=tuple(sorted(sources)),
        units=tuple(
            SourceUnit(path, Path("/project") / path, text, "digest-" + path)
            for path, text in sorted(sources.items())
        ),
        issues=(),
    )
    return build_python_program(collection).modules


def test_expression_payload_does_not_increase_nested_import_walk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = ", ".join(f"transform({index})" for index in range(500))
    modules = _modules(
        f"def load():\n    payload = [{payload}]\n"
        "    from backends import alpha as chosen\n    return chosen\n"
    )
    original = ast.iter_child_nodes
    expression_visits = 0

    def counted(node: ast.AST) -> Iterator[ast.AST]:
        nonlocal expression_visits
        if isinstance(node, ast.expr):
            expression_visits += 1
        return original(node)

    monkeypatch.setattr(ast, "iter_child_nodes", counted)

    assert _nested_module_imports(modules["main"], modules) == {"chosen": "backends.alpha"}
    assert expression_visits == 0


def test_handler_and_match_containers_preserve_breadth_first_alias_order() -> None:
    modules = _modules("""
def load():
    try:
        if condition:
            from backends import alpha as chosen
    except* ValueError:
        from backends import beta as chosen
    match value:
        case _:
            from backends import gamma as chosen
    def nested():
        from backends import delta as chosen
""")

    # delta is shallower than the three other imports. At their equal depth,
    # gamma follows alpha and beta. Flattening handlers/cases changes this order.
    assert _nested_module_imports(modules["main"], modules) == {"chosen": "backends.gamma"}


def test_nested_statement_containers_and_outer_definition_boundary() -> None:
    modules = _modules("""
from backends import delta as top_level
if condition:
    def conditional():
        from backends import delta as outside_roots
class Registry:
    from backends import alpha as in_class
    async def load(self):
        async with resource():
            from backends import alpha as in_with
        async for item in items():
            import backends.beta as in_for
        while condition:
            from backends import gamma as in_while
        try:
            from backends import alpha as in_try
        except ValueError:
            from backends import beta as in_except
        else:
            from backends import gamma as in_else
        finally:
            from backends import delta as in_finally
""")

    assert _nested_module_imports(modules["main"], modules) == {
        "in_class": "backends.alpha",
        "in_with": "backends.alpha",
        "in_for": "backends.beta",
        "in_while": "backends.gamma",
        "in_try": "backends.alpha",
        "in_except": "backends.beta",
        "in_else": "backends.gamma",
        "in_finally": "backends.delta",
    }
