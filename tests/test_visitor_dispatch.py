"""Dispatch binds only a selected callback and never retains a visitor in a table."""

from __future__ import annotations

import ast
import weakref
from typing import Any

from deadtrace.python_frontend import _ExecutionVisitor


class _DispatchProbe(_ExecutionVisitor):
    def __init__(self) -> None:
        self.bindings: dict[str, int] = {}
        self.seen: list[ast.AST] = []
        self._handled = set()

    def __getattribute__(self, name: str) -> Any:
        if (
            name.startswith("_visit_") and name != "_visit_nodes"
        ) or name == "visit_definition_header":
            bindings = object.__getattribute__(self, "bindings")
            bindings[name] = bindings.get(name, 0) + 1
        return object.__getattribute__(self, name)

    def _visit_name_or_attribute(self, node: ast.expr) -> None:
        self.seen.append(node)
        self._handled.add(id(node))

    def _visit_constant(self, node: ast.Constant) -> None:
        self.seen.append(node)
        self._handled.add(id(node))


def test_empty_or_unhandled_input_binds_no_callbacks() -> None:
    visitor = _DispatchProbe()
    visitor._visit_nodes(())
    visitor._visit_nodes((ast.Pass(),))
    assert sum(visitor.bindings.values()) == 0
    assert visitor.seen == []


def test_only_selected_callbacks_are_bound_in_order_and_handled_nodes_are_skipped() -> None:
    visitor = _DispatchProbe()
    name, constant = ast.Name(id="value", ctx=ast.Load()), ast.Constant(value=1)
    visitor._visit_nodes((name, ast.Pass(), constant, name))
    assert visitor.seen == [name, constant]
    assert visitor.bindings == {"_visit_name_or_attribute": 1, "_visit_constant": 1}


def test_dispatch_metadata_does_not_keep_a_visitor_alive() -> None:
    visitor = _DispatchProbe()
    reference = weakref.ref(visitor)
    visitor._visit_nodes(())
    del visitor
    assert reference() is None
