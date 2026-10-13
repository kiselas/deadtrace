from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest

from deadtrace import python_frontend
from deadtrace.python_frontend import PythonModule, build_python_program
from deadtrace.scanner import SourceCollection, SourceUnit


def test_module_value_projections_share_one_scan_without_prefix_pollution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sources = {
        "backends/__init__.py": "",
        "backends/literal.py": "def perform():\n    return 1\n",
        "backends/computed.py": "def perform():\n    return 2\n",
        "main.py": (
            "from importlib import import_module\n"
            "def modules():\n    from backends import literal\n    return (literal,)\n"
            "def load(name):\n    return import_module('backends.' + name)\n"
        ),
    }
    collection = SourceCollection(
        root=Path("/project"),
        files=tuple(sorted(sources)),
        units=tuple(
            SourceUnit(path, Path("/project") / path, source, "digest-" + path)
            for path, source in sorted(sources.items())
        ),
        issues=(),
    )
    program = build_python_program(collection)
    resolver = python_frontend._Resolver(program.modules, program.symbols, program.index)
    original = python_frontend._nested_module_imports
    scans = 0

    def counted(module: PythonModule, modules: Mapping[str, PythonModule]) -> dict[str, str]:
        nonlocal scans
        scans += 1
        return original(module, modules)

    monkeypatch.setattr(python_frontend, "_nested_module_imports", counted)
    literal = program.resolve_symbol("backends.literal.perform")
    computed = program.resolve_symbol("backends.computed.perform")
    assert literal is not None and computed is not None
    named = resolver.value_module_members_named("perform")
    assert literal.id in named and computed.id in named
    universe, _ = resolver.member_universe()
    assert literal.id in universe
    assert computed.id not in universe, "computed prefix contaminated directly held modules"
    assert scans == len(program.modules)
