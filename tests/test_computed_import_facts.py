"""Computed-import projections share traversal while preserving their distinct boundaries."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

import pytest

from deadtrace import python_frontend
from deadtrace.scanner import SourceCollection, SourceUnit


def _program(source: str) -> python_frontend.PythonProgram:
    sources = {
        "main.py": "def perform():\n    return 0\n" + source,
        "plugins/__init__.py": "",
        "plugins/alpha.py": "def perform():\n    return 1\n",
        "plugins/beta.py": "def perform():\n    return 2\n",
        "other.py": "def perform():\n    return 3\n",
    }
    root = Path("/project")
    return python_frontend.build_python_program(
        SourceCollection(
            root=root,
            files=tuple(sorted(sources)),
            units=tuple(
                SourceUnit(path, root / path, text, "owned-" + path)
                for path, text in sorted(sources.items())
            ),
            issues=(),
        )
    )


def test_syntax_and_computed_import_queries_visit_payload_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = ", ".join(f"convert({index})" for index in range(500))
    program = _program(
        f"def load(name):\n    values = [{payload}]\n    return import_module(name)\n"
    )
    module = program.modules["main"]
    marker = next(node for node in ast.walk(module.tree) if isinstance(node, ast.List))
    original = ast.iter_child_nodes
    visits = 0
    empty_leaf_visits = 0

    def counted(node: ast.AST) -> Iterator[ast.AST]:
        nonlocal visits, empty_leaf_visits
        if node is marker:
            visits += 1
        if not node._fields:
            empty_leaf_visits += 1
        return original(node)

    monkeypatch.setattr(ast, "iter_child_nodes", counted)
    resolver = python_frontend._Resolver(program.modules, program.symbols, program.index)
    for _ in range(2):
        assert resolver.imports_computed_modules()
        assert len(resolver.value_module_members_named("perform")) == 4
        assert resolver.functions_with_scope_constructs(module) == frozenset()
    assert visits == 1
    assert empty_leaf_visits == 0


@pytest.mark.parametrize(
    ("expression", "computed", "scope"),
    [
        ('import_module("plugins.alpha")', False, "none"),
        ('import_module("plugins." + name)', True, "plugins"),
        ('importlib.import_module(f"plugins.{name}")', True, "plugins"),
        ('import_module(f"plugins.alpha")', True, "alpha"),
        ("__import__(name)", True, "all"),
        ("__import__()", True, "all"),
        ("import_module(None)", True, "all"),
        ("sys.modules[__name__]", True, "self"),
        ("other.modules.get(name)", True, "all"),
        ("sys.modules.get()", True, "all"),
        ('__import__("sys").modules[name]', True, "all"),
        ('sys.modules["plugins.alpha"]', False, "none"),
        ('sys.modules.get("plugins.alpha")', False, "none"),
        ('import_module(".plugins." + name)', True, "all"),
        ('sys.modules[".plugins." + name]', True, "none"),
        ("cache.get(name)", False, "none"),
        ("user.import_module(name)", False, "none"),
        ("builtins.__import__(name)", False, "none"),
        ('getattr(sys, "modules")[name]', False, "none"),
        # Fullwidth identifiers normalize in AST without the raw ASCII hints.
        ("ｉｍｐｏｒｔ＿ｍｏｄｕｌｅ(name)", True, "none"),  # noqa: RUF001
        ("sys.ｍｏｄｕｌｅｓ[name]", True, "none"),  # noqa: RUF001
    ],
)
def test_prefixes_and_project_flag_keep_separate_existing_boundaries(
    expression: str,
    computed: bool,
    scope: str,
) -> None:
    program = _program(f"def load(name):\n    return {expression}\n")
    resolver = python_frontend._Resolver(program.modules, program.symbols, program.index)
    expected = {
        "none": set(),
        "plugins": {"plugins.alpha", "plugins.beta"},
        "alpha": {"plugins.alpha"},
        "self": {"main"},
        "all": {"main", "other", "plugins.alpha", "plugins.beta"},
    }[scope]
    assert resolver.imports_computed_modules() is computed
    assert {
        program.symbols[node].module for node in resolver.value_module_members_named("perform")
    } == expected
