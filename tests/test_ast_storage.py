"""Storage changes preserve the running interpreter's complete AST, without execution."""

import ast
import copy
import pickle
import platform
import sys

import pytest

from deadtrace.inventory import parse_source


def test_compaction_preserves_nodes_attribute_values_and_order() -> None:
    from deadtrace.inventory import _compact_ast_attributes

    source = """
class Registry[T]:
    async def process(self, values: list[T]):
        try:
            result = [await handler(value) for value in values if value]
        except* ValueError as errors:
            result = errors
        match result:
            case {"data": [first, *rest]}:
                return f"{first!r}: {rest}"
            case _:
                return None
"""
    tree = ast.parse(source)
    before_dump = ast.dump(tree, include_attributes=True)
    before_nodes = list(ast.walk(tree))
    before_attributes = [list(vars(node).items()) for node in before_nodes]

    _compact_ast_attributes(tree)

    assert list(ast.walk(tree)) == before_nodes
    for node, before in zip(before_nodes, before_attributes, strict=True):
        after = list(vars(node).items())
        assert [name for name, _ in after] == [name for name, _ in before]
        assert all(old is new for (_, old), (_, new) in zip(before, after, strict=True))
    assert ast.dump(tree, include_attributes=True) == before_dump
    assert ast.dump(copy.deepcopy(tree), include_attributes=True) == before_dump
    assert ast.dump(pickle.loads(pickle.dumps(tree)), include_attributes=True) == before_dump


@pytest.mark.skipif(platform.python_implementation() != "CPython", reason="CPython storage budget")
def test_repeated_nodes_share_attribute_keys_with_a_smaller_storage_budget() -> None:
    source = "def convert(value: int):\n    return value + 1\n" * 1000
    ordinary = ast.parse(source)
    compact = parse_source(source).tree
    ordinary_bytes = sum(sys.getsizeof(vars(node)) for node in ast.walk(ordinary))
    compact_bytes = sum(sys.getsizeof(vars(node)) for node in ast.walk(compact))

    assert ast.dump(compact, include_attributes=True) == ast.dump(ordinary, include_attributes=True)
    assert compact_bytes < ordinary_bytes * 0.65


def test_separate_parses_keep_their_own_attribute_dictionaries() -> None:
    first = parse_source('value = "ё"\n')
    second = parse_source('value = "日本"\n')
    first_assignment = first.tree.body[0]
    second_assignment = second.tree.body[0]
    assert isinstance(first_assignment, ast.Assign)
    assert isinstance(second_assignment, ast.Assign)
    assert vars(first_assignment) is not vars(second_assignment)
    assert ast.get_source_segment(first.text.text, first_assignment.value) == '"ё"'
    assert ast.get_source_segment(second.text.text, second_assignment.value) == '"日本"'
