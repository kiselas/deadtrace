"""Read/serialization compatibility and retained allocation budget of AST storage."""

from __future__ import annotations

import ast
import copy
import gc
import pickle
import platform
import sys
import tracemalloc
import weakref
from collections.abc import Callable

import pytest

from deadtrace.inventory import _compact_ast_attributes, parse_source


def _current_storage(source: str) -> ast.Module:
    tree = ast.parse(source)
    _compact_ast_attributes(tree)
    return tree


def _retained_bytes(parse: Callable[[str], ast.Module], source: str) -> int:
    gc.collect()
    tracemalloc.start()
    try:
        tree = parse(source)
        gc.collect()
        current, _ = tracemalloc.get_traced_memory()
        assert isinstance(tree, ast.Module)
        return current
    finally:
        tracemalloc.stop()


@pytest.mark.skipif(
    platform.python_implementation() != "CPython", reason="CPython allocation budget"
)
def test_slotted_tree_retains_less_than_grammar_shared_dictionaries() -> None:
    source = "def convert(value: int):\n    return value + 1\n" * 1000
    _current_storage(source)
    parse_source(source)
    ordinary = _retained_bytes(_current_storage, source)
    packed = _retained_bytes(lambda text: parse_source(text).tree, source)

    assert packed < ordinary * 0.85, (ordinary, packed)


def test_all_fields_types_names_and_locations_match_stdlib() -> None:
    source = """
class Registry[T]:
    async def process(self, values: list[T], **kwargs):
        try:
            result = [await handler(value) for value in values if value]
        except* ValueError as errors:
            result = errors
        match result:
            case {"data": [first, *rest]} if rest:
                return f"{first!r}: {rest}"
            case _:
                return None
"""
    ordinary = ast.parse(source)
    packed = parse_source(source).tree
    expected = ast.dump(ordinary, include_attributes=True)

    assert ast.dump(packed, include_attributes=True) == expected
    assert ast.dump(copy.deepcopy(packed), include_attributes=True) == expected
    assert ast.dump(pickle.loads(pickle.dumps(packed)), include_attributes=True) == expected
    for old, new in zip(ast.walk(ordinary), ast.walk(packed), strict=True):
        assert isinstance(new, type(old))
        assert type(new).__name__ == type(old).__name__
        for name in (*old._fields, *old._attributes):
            assert hasattr(new, name) == hasattr(old, name)
            if hasattr(old, name) and not isinstance(getattr(old, name), (ast.AST, list)):
                assert getattr(new, name) == getattr(old, name)
        if isinstance(new, ast.Name):
            assert type(new.ctx) in {ast.Load, ast.Store, ast.Del}


def test_optional_none_defaults_keep_dump_and_class_attribute_behavior() -> None:
    ordinary = ast.parse("def empty():\n    return None\n")
    packed = parse_source("def empty():\n    return None\n").tree
    assert ast.dump(packed, include_attributes=True) == ast.dump(ordinary, include_attributes=True)
    for node in ast.walk(packed):
        if isinstance(node, ast.FunctionDef):
            assert node.returns is None and type(node).returns is None
        if isinstance(node, ast.arguments):
            assert node.vararg is None and type(node).vararg is None


def test_releasing_parsed_tree_does_not_retain_nodes_in_grammar_registry() -> None:
    parsed = parse_source('def marker():\n    return "marker value"\n')
    module = weakref.ref(parsed.tree)
    function = weakref.ref(parsed.tree.body[0])
    del parsed
    gc.collect()
    assert module() is None and function() is None


@pytest.mark.skipif(sys.version_info < (3, 14), reason="template strings require the 3.14 grammar")
def test_template_string_fields_follow_the_running_interpreter() -> None:
    source = 'message = t"{marker} {value!r:>12}"\n'
    ordinary = ast.parse(source)
    packed = parse_source(source).tree
    expected = ast.dump(ordinary, include_attributes=True)
    assert ast.dump(packed, include_attributes=True) == expected
    assert ast.dump(pickle.loads(pickle.dumps(packed)), include_attributes=True) == expected
