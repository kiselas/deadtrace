"""Module syntax projections share traversal without changing lexical boundaries."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

import pytest

from deadtrace import python_frontend
from deadtrace.scanner import SourceCollection, SourceUnit


def _program(source: str) -> python_frontend.PythonProgram:
    collection = SourceCollection(
        root=Path("/project"),
        files=("main.py",),
        units=(SourceUnit("main.py", Path("/project/main.py"), source, "owned-source"),),
        issues=(),
    )
    return python_frontend.build_python_program(collection)


def test_resolver_syntax_projections_visit_expression_payload_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = ", ".join(f"transform({index})" for index in range(500))
    program = _program(f"def process():\n    values = [{payload}]\n    return values\n")
    module = program.modules["main"]
    marker = next(node for node in ast.walk(module.tree) if isinstance(node, ast.List))
    original = ast.iter_child_nodes
    visits = 0

    def counted(node: ast.AST) -> Iterator[ast.AST]:
        nonlocal visits
        if node is marker:
            visits += 1
        return original(node)

    monkeypatch.setattr(ast, "iter_child_nodes", counted)
    resolver = python_frontend._Resolver(program.modules, program.symbols, program.index)
    assert resolver.functions_with_scope_constructs(module) == frozenset()
    assert resolver.functions_with_scope_constructs(module) == frozenset()
    assert visits == 1


def test_syntax_facts_preserve_nested_function_and_store_boundaries() -> None:
    program = _program("""
from toolkit import *
module_value = 1
def ordinary(value):
    return value
def outer():
    state = 1
    class Carrier:
        field = 1
        def inner(self):
            nonlocal state
            global module_value
            self.service = [value for value in values if (saved := value)]
            registry[index].ignored = 2
    return Carrier
async def asynchronous():
    return {value: value async for value in stream}
""")
    module = program.modules["main"]
    resolver = python_frontend._Resolver(program.modules, program.symbols, program.index)
    functions = {
        node.name: id(node)
        for node in ast.walk(module.tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert resolver.functions_with_scope_constructs(module) == frozenset(
        functions[name] for name in ("outer", "inner", "asynchronous")
    )
    assert resolver._modules_with_star_imports == frozenset({"main"})
    assert resolver._nominal_rebindings["main"] == frozenset(
        {"module_value", "state", "field", "self.service", "value", "saved"}
    )


def test_function_decorator_and_default_keep_original_scope_classification() -> None:
    program = _program("""
def outer():
    @decorate((tag := 1))
    def decorated(value=[item for item in values]):
        return value
    def plain():
        return 1
    return decorated
""")
    module = program.modules["main"]
    resolver = python_frontend._Resolver(program.modules, program.symbols, program.index)
    expected = frozenset(
        id(node)
        for node in ast.walk(module.tree)
        if isinstance(node, ast.FunctionDef) and node.name in {"outer", "decorated"}
    )
    assert resolver.functions_with_scope_constructs(module) == expected
