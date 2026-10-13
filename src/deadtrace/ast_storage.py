"""Compact AST storage after stdlib parsing; never import or execute source code."""

from __future__ import annotations

import ast
from typing import Any, cast


class _SlotMeta(type):
    def __getattribute__(cls, name: str) -> Any:
        # ast.dump omits optional None fields based on the class default. The
        # instance still resolves the slot descriptor directly, without this hook.
        defaults = cast(frozenset[str], type.__getattribute__(cls, "_none_defaults"))
        if name in defaults:
            return None
        return type.__getattribute__(cls, name)


def _restore_native(node_type: type[ast.AST], state: dict[str, object]) -> ast.AST:
    """Pickle/deepcopy return ordinary stdlib nodes with complete field values."""

    return node_type(**state)


def _reduce_node(node: ast.AST, protocol: int) -> tuple[object, tuple[object, ...]]:
    node_type = type.__getattribute__(type(node), "_native_type")
    state = {
        name: getattr(node, name)
        for name in (*node._fields, *node._attributes)
        if hasattr(node, name)
    }
    state.update(vars(node))
    return _restore_native, (node_type, state)


def _slot_types() -> dict[type[ast.AST], type[ast.AST]]:
    result: dict[type[ast.AST], type[ast.AST]] = {}
    for node_type in vars(ast).values():
        # Deprecated aliases with a custom metaclass are never emitted by parse.
        # Empty-field context/operator singletons keep their exact stdlib types.
        if type(node_type) is type and issubclass(node_type, ast.AST) and node_type._fields:
            names = tuple(dict.fromkeys((*node_type._fields, *node_type._attributes)))
            defaults = frozenset(name for name in names if getattr(node_type, name, ...) is None)
            result[node_type] = cast(
                type[ast.AST],
                _SlotMeta(
                    node_type.__name__,
                    (node_type,),
                    {
                        "__slots__": names,
                        "_none_defaults": defaults,
                        "_native_type": node_type,
                        "__reduce_ex__": _reduce_node,
                    },
                ),
            )
    return result


_SLOT_TYPES = _slot_types()
_NATIVE_TYPES = {packed: native for native, packed in _SLOT_TYPES.items()}


def native_type(node: ast.AST) -> type[ast.AST]:
    """Canonical stdlib class for dispatch tables keyed by exact node type."""

    node_type = type(node)
    return _NATIVE_TYPES.get(node_type, node_type)


def compact_tree(tree: ast.AST) -> ast.AST:
    """Rebuild one file before publishing it as the immutable parsed input.

    Grammar metadata survives analyses; values and conversion maps do not. Nodes
    remain instances of their stdlib classes, with the same names/fields/locations.
    The worklist avoids recursive conversion of deeply nested expression trees.
    """

    converted: dict[int, ast.AST] = {}
    pending: list[tuple[ast.AST, ast.AST]] = []

    def allocate(node: ast.AST) -> ast.AST:
        node_type = _SLOT_TYPES.get(type(node))
        if node_type is None:
            return node
        found = converted.get(id(node))
        if found is not None:
            return found
        clone = ast.AST.__new__(node_type)
        converted[id(node)] = clone
        pending.append((node, clone))
        return clone

    result = allocate(tree)
    while pending:
        node, clone = pending.pop()
        for name, value in vars(node).items():
            if isinstance(value, ast.AST):
                value = allocate(value)
            elif isinstance(value, list):
                value = [allocate(item) if isinstance(item, ast.AST) else item for item in value]
            setattr(clone, name, value)
    return result
