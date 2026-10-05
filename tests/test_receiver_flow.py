"""Independent receiver-flow safety and locality checks, without executing the sources."""

from __future__ import annotations

from pathlib import Path
from textwrap import indent

import pytest

from deadtrace.core import ReachabilityKind, WorldId, WorldPlan, solve
from deadtrace.python_frontend import build_python_program
from deadtrace.scanner import SourceCollection, SourceUnit


def _states(body: str, *, extra: str = "") -> dict[str, ReachabilityKind | None]:
    source = "from __future__ import annotations\n" + (
        """
class First:
    def run(self): return 1
    def other(self): return 0
    def change(self) -> Second: return Second()
class Second:
    def run(self): return 2
    def other(self): return 0
    def change(self) -> First: return First()
class Third:
    def run(self): return 3
    def other(self): return 0
"""
        + extra
        + "\ndef main(flag, unknown):\n"
        + indent(body, "    ")
    )
    collection = SourceCollection(
        root=Path("/project"),
        files=("main.py",),
        units=(SourceUnit("main.py", Path("/project/main.py"), source, "flow-digest"),),
        issues=(),
    )
    program = build_python_program(collection)
    root = program.resolve_symbol("main:main")
    assert root is not None
    world_id = WorldId("production", "script")
    world = solve(
        program.graph, (WorldPlan(world_id, (root.id, program.modules["main"].node_id)),)
    ).world(world_id)
    return {symbol.qualified_name: world.state_of(symbol.id) for symbol in program.symbols.values()}


@pytest.mark.parametrize("left,right", [("First", "Second"), ("Second", "First")])
@pytest.mark.parametrize("alias", [False, True])
def test_branch_order_and_aliases_keep_both_receivers_locally(
    left: str, right: str, alias: bool
) -> None:
    body = f"if flag:\n    item = {left}()\nelse:\n    item = {right}()\n"
    body += "other = item\nother.run()\n" if alias else "item.run()\n"
    states = _states(body)
    assert states["First.run"] is ReachabilityKind.RESOLVED
    assert states["Second.run"] is ReachabilityKind.RESOLVED
    assert states["Third.run"] is None
    assert all(states[f"{name}.other"] is None for name in ("First", "Second", "Third"))


@pytest.mark.parametrize(
    "body",
    [
        "item = First()\nif flag:\n    item = Second()\nitem.run()\n",
        "item = First() if flag else Second()\nitem.run()\n",
        "item = First()\nfor value in unknown:\n    item.run()\n    item = Second()\n",
        "item = First()\nwhile flag:\n    item.run()\n    item = Second()\n",
        "item = First()\nwhile flag:\n    item = Second()\n    continue\nitem.run()\n",
        "item = First()\nfor value in unknown:\n    if flag:\n        break\n"
        "    item = Second()\nelse:\n    item = Third()\nitem.run()\n",
    ],
)
def test_missing_branches_zero_iterations_and_back_edges_preserve_types(body: str) -> None:
    states = _states(body)
    assert states["First.run"] is ReachabilityKind.RESOLVED
    assert states["Second.run"] is ReachabilityKind.RESOLVED
    assert all(states[f"{name}.other"] is None for name in ("First", "Second", "Third"))


def test_straight_line_overwrite_does_not_retain_obsolete_methods() -> None:
    states = _states("item = First()\nitem = Second()\nitem.run()\n")
    assert states["First.run"] is None
    assert states["Second.run"] is ReachabilityKind.RESOLVED
    assert states["Third.run"] is None


def test_assignment_evaluates_its_rhs_before_replacing_the_receiver() -> None:
    states = _states("item = First()\nitem = item.change()\nitem.run()\n")
    assert states["First.change"] is ReachabilityKind.RESOLVED
    assert states["First.run"] is None
    assert states["Second.run"] is ReachabilityKind.RESOLVED


@pytest.mark.parametrize(
    "body",
    [
        "item = First()\nitem = unknown\nitem.run()\n",
        "item = First()\nif flag:\n    item = unknown\nitem.run()\n",
        "item = First()\nitem += unknown\nitem.run()\n",
        "item = First()\ndel item\nitem = unknown\nitem.run()\n",
        "item = First()\nitem, value = unknown\nitem.run()\n",
        "item = First()\nfor item in unknown:\n    item.run()\n",
        "item = First()\nwith unknown as item:\n    item.run()\n",
        "item = First()\nmatch unknown:\n    case {'value': item}:\n        item.run()\n",
        "item = First()\nif (item := unknown):\n    item.run()\n",
    ],
)
def test_unknown_writes_cannot_reuse_stale_types(body: str) -> None:
    states = _states(body)
    assert states["Third.run"] is ReachabilityKind.CONSERVATIVE
    assert states["Third.other"] is None


def test_exception_handler_and_finally_see_intermediate_writes() -> None:
    states = _states("""item = First()
try:
    if flag:
        item = Second()
        unknown()
        item = First()
except Exception:
    item.run()
finally:
    item.run()
""")
    assert states["First.run"] is not None
    assert states["Second.run"] is not None
    assert states["Third.other"] is None


def test_dynamic_getattr_uses_the_union_of_known_receivers() -> None:
    states = _states("""if flag:
    item = First()
else:
    item = Second()
getattr(item, unknown)()
""")
    assert states["First.run"] is ReachabilityKind.CONSERVATIVE
    assert states["Second.run"] is ReachabilityKind.CONSERVATIVE
    assert states["Third.run"] is None


def test_fixed_point_budget_widens_without_losing_possible_methods() -> None:
    # Information advances one variable per iteration; 40 steps exceed the budget of 32.
    setup = "\n".join(f"item{i} = First()" for i in range(40))
    shifts = "\n".join(f"    item{i} = item{i - 1}" for i in reversed(range(1, 40)))
    body = setup + "\nwhile flag:\n    item39.run()\n" + shifts + "\n    item0 = Second()\n"
    states = _states(body)
    assert states["First.run"] is not None
    assert states["Second.run"] is not None
    assert states["Third.other"] is None


def test_scope_budget_is_shared_across_nested_and_sequential_loops() -> None:
    prefix = "\n".join("for value in unknown:\n    pass" for _ in range(260))
    states = _states(
        prefix + "\nitem = First()\nwhile flag:\n    item.run()\n    item = Second()\n"
    )
    assert states["First.run"] is not None
    assert states["Second.run"] is not None
    assert states["Third.other"] is None


def test_assignment_target_expressions_still_execute() -> None:
    states = _states(
        "make().attribute = 1\n",
        extra="\ndef make():\n    return First()\n",
    )
    assert states["make"] is ReachabilityKind.RESOLVED


def test_joined_instances_escape_with_all_possible_classes() -> None:
    states = _states("""if flag:
    item = First()
else:
    item = Second()
unknown(item)
""")
    assert states["First.run"] is not None
    assert states["Second.run"] is not None
    assert states["Third.run"] is None


def test_call_results_preserve_alternative_receiver_return_annotations() -> None:
    states = _states("""if flag:
    item = First()
else:
    item = Second()
result = item.change()
result.run()
""")
    assert states["First.run"] is ReachabilityKind.RESOLVED
    assert states["Second.run"] is ReachabilityKind.RESOLVED
    assert states["Third.run"] is None
