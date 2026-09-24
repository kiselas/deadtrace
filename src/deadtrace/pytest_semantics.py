"""Static pytest collection and fixture semantics for an isolated tests world."""

from __future__ import annotations

import ast
from dataclasses import dataclass, replace
from pathlib import PurePosixPath

from deadtrace.config import Config
from deadtrace.core import (
    AssemblyState,
    EdgeKind,
    ExecutionEdge,
    Limitation,
    NodeId,
    Requirement,
    SemanticGraph,
    UnknownBoundary,
    WorldId,
    WorldPlan,
)
from deadtrace.frameworks import FrameworkCapability, FrameworkModel
from deadtrace.python_frontend import (
    PythonModule,
    PythonProgram,
    PythonSymbol,
    _dotted_name,
    call_arguments,
    is_function,
    keyword_argument,
    single_string_literal,
)

_BUILTIN_FIXTURES = frozenset(
    {
        "cache",
        "capfd",
        "capfdbinary",
        "caplog",
        "capsys",
        "capsysbinary",
        "doctest_namespace",
        "monkeypatch",
        "pytestconfig",
        "record_property",
        "record_testsuite_property",
        "record_xml_attribute",
        "recwarn",
        "request",
        "tmp_path",
        "tmp_path_factory",
        "tmpdir",
        "tmpdir_factory",
    }
)


@dataclass(frozen=True, slots=True)
class Fixture:
    name: str
    symbol: NodeId
    module: str
    path: str
    autouse: bool
    dependencies: tuple[str, ...]


def apply_pytest_model(
    program: PythonProgram, model: FrameworkModel, config: Config
) -> FrameworkModel:
    """Add one isolated pytest world when statically collectable tests exist."""

    del config
    tests = tuple(
        symbol
        for symbol in program.symbols.values()
        if _is_test_symbol(symbol) and _is_test_path(symbol.path)
    )
    if not tests:
        return model

    fixtures = _discover_fixtures(program)
    edges = list(model.graph.edges)
    requirements = list(model.graph.requirements)
    boundaries = list(model.graph.boundaries)
    roots: set[NodeId] = set()
    limitations: list[Limitation] = []
    world = WorldId("tests", "pytest")
    all_nodes = tuple(node.id for node in model.graph.nodes)

    for test in tests:
        roots.add(test.id)
        roots.add(program.modules[test.module].node_id)
        visible = _visible_fixtures(test.path, test.module, fixtures)
        parameterized = _parameterized_names(program.modules[test.module], test)
        requested = {
            parameter.name
            for parameter in test.parameters
            if parameter.name not in {"self", "cls"} and parameter.name not in parameterized
        }
        requested.update(_usefixtures_names(program.modules[test.module], test))
        requested.update(fixture.name for fixture in visible.values() if fixture.autouse)
        _connect_fixture_requests(
            source=test.id,
            requested=requested,
            visible=visible,
            edges=edges,
            boundaries=boundaries,
            limitations=limitations,
            world=world,
            all_nodes=all_nodes,
        )
        for fixture in visible.values():
            requirements.append(
                Requirement(
                    source=program.modules[test.module].node_id,
                    target=fixture.symbol,
                    kind=EdgeKind.FRAMEWORK,
                    detail=f"pytest fixture {fixture.name} is visible to {test.qualified_name}",
                )
            )

    for fixture in fixtures:
        visible = _visible_fixtures(fixture.path, fixture.module, fixtures)
        _connect_fixture_requests(
            source=fixture.symbol,
            requested=set(fixture.dependencies),
            visible=visible,
            edges=edges,
            boundaries=boundaries,
            limitations=limitations,
            world=world,
            all_nodes=all_nodes,
        )

    plugin_limitations = _pytest_plugin_limitations(program, world)
    limitations.extend(plugin_limitations)
    assembly = AssemblyState.PARTIAL if limitations else AssemblyState.COMPLETE
    test_plan = WorldPlan(
        id=world,
        roots=tuple(sorted(roots)),
        assembly_state=assembly,
        limitations=tuple(sorted(set(limitations), key=_limitation_sort_key)),
    )
    plans = (*(plan for plan in model.plans if plan.id != world), test_plan)
    graph = SemanticGraph(
        nodes=model.graph.nodes,
        edges=tuple(sorted(set(edges), key=_edge_sort_key)),
        requirements=tuple(sorted(set(requirements), key=_requirement_sort_key)),
        boundaries=tuple(sorted(set(boundaries), key=_boundary_sort_key)),
    )
    return replace(
        model,
        graph=graph,
        plans=tuple(sorted(plans, key=lambda item: item.id)),
        capabilities=(
            *model.capabilities,
            FrameworkCapability("pytest.fixtures", 1, "modeled"),
        ),
    )


def _discover_fixtures(program: PythonProgram) -> tuple[Fixture, ...]:
    fixtures: list[Fixture] = []
    for symbol in program.symbols.values():
        if not is_function(symbol):
            continue
        module = program.modules[symbol.module]
        for expression in symbol.decorators:
            function = expression.func if isinstance(expression, ast.Call) else expression
            if not _expanded_name(module, function).endswith("pytest.fixture"):
                continue
            fixture_name = symbol.name
            autouse = False
            if isinstance(expression, ast.Call):
                name_value = single_string_literal(_keyword(expression, "name"), module.text)
                if name_value is not None:
                    fixture_name = name_value
                autouse_value = _keyword(expression, "autouse")
                autouse = _dotted_name(autouse_value) == "True"
            dependencies = tuple(
                parameter.name
                for parameter in symbol.parameters
                if parameter.name not in {"self", "cls", "request"}
            )
            fixtures.append(
                Fixture(
                    name=fixture_name,
                    symbol=symbol.id,
                    module=symbol.module,
                    path=symbol.path,
                    autouse=autouse,
                    dependencies=dependencies,
                )
            )
            break
    return tuple(sorted(fixtures, key=lambda item: (item.path, item.name, str(item.symbol))))


def _visible_fixtures(
    consumer_path: str,
    consumer_module: str,
    fixtures: tuple[Fixture, ...],
) -> dict[str, Fixture]:
    consumer_parent = PurePosixPath(consumer_path).parent
    visible: dict[str, Fixture] = {}
    for fixture in fixtures:
        fixture_path = PurePosixPath(fixture.path)
        same_module = fixture.module == consumer_module
        conftest_visible = fixture_path.name == "conftest.py" and _is_parent(
            fixture_path.parent, consumer_parent
        )
        if same_module or conftest_visible:
            visible[fixture.name] = fixture
    return visible


def _connect_fixture_requests(
    *,
    source: NodeId,
    requested: set[str],
    visible: dict[str, Fixture],
    edges: list[ExecutionEdge],
    boundaries: list[UnknownBoundary],
    limitations: list[Limitation],
    world: WorldId,
    all_nodes: tuple[NodeId, ...],
) -> None:
    for name in sorted(requested):
        fixture = visible.get(name)
        if fixture is not None:
            edges.append(
                ExecutionEdge(
                    source,
                    fixture.symbol,
                    EdgeKind.DEPENDENCY,
                    f"pytest resolves fixture {name}",
                )
            )
        elif name not in _BUILTIN_FIXTURES:
            limitations.append(
                Limitation(
                    code="DT3201",
                    message=f"pytest fixture or parametrization cannot be resolved: {name}",
                    origin=source,
                    world=world,
                )
            )
            boundaries.append(
                UnknownBoundary(
                    source=source,
                    domain="pytest_fixture_resolution",
                    reason=f"unresolved pytest fixture {name}",
                    targets=all_nodes,
                )
            )


def _is_test_symbol(symbol: PythonSymbol) -> bool:
    if not is_function(symbol):
        return False
    if symbol.name.startswith("test_"):
        return symbol.owner_qualified_name is None or symbol.owner_qualified_name.split(".")[
            0
        ].startswith("Test")
    return False


def _is_test_path(path: str) -> bool:
    name = PurePosixPath(path).name
    return name.startswith("test_") or name.endswith("_test.py")


def _usefixtures_names(module: PythonModule, symbol: PythonSymbol) -> set[str]:
    names: set[str] = set()
    for expression in symbol.decorators:
        if not isinstance(expression, ast.Call) or not _expanded_name(
            module, expression.func
        ).endswith("pytest.mark.usefixtures"):
            continue
        for argument in call_arguments(expression):
            value = single_string_literal(argument.value, module.text)
            if value is not None:
                names.add(value)
    return names


def _parameterized_names(module: PythonModule, symbol: PythonSymbol) -> set[str]:
    names: set[str] = set()
    for expression in symbol.decorators:
        if not isinstance(expression, ast.Call) or not _expanded_name(
            module, expression.func
        ).endswith("pytest.mark.parametrize"):
            continue
        arguments = call_arguments(expression)
        evaluated = single_string_literal(arguments[0].value, module.text) if arguments else None
        if evaluated is not None:
            names.update(part.strip() for part in evaluated.split(",") if part.strip())
    return names


def _pytest_plugin_limitations(program: PythonProgram, world: WorldId) -> list[Limitation]:
    limitations: list[Limitation] = []
    for module in program.modules.values():
        for small in module.tree.body:
            if not (
                isinstance(small, ast.Assign)
                and any(
                    isinstance(target, ast.Name) and target.id == "pytest_plugins"
                    for target in small.targets
                )
            ):
                continue
            limitations.append(
                Limitation(
                    code="DT3202",
                    message="pytest_plugins collection is not modeled yet",
                    origin=module.node_id,
                    world=world,
                )
            )
    return limitations


def _expanded_name(module: PythonModule, expression: ast.AST | None) -> str:
    dotted = _dotted_name(expression)
    if dotted is None:
        return ""
    first, *rest = dotted.split(".")
    binding = module.imports.get(first)
    if binding is None:
        return f"{module.name}.{dotted}"
    return ".".join((binding.target, *rest)) if rest else binding.target


def _keyword(call: ast.Call, name: str) -> ast.expr | None:
    return keyword_argument(call, name)


def _is_parent(parent: PurePosixPath, child: PurePosixPath) -> bool:
    return parent == child or parent in child.parents


def _edge_sort_key(edge: ExecutionEdge) -> tuple[str, ...]:
    return (str(edge.source), str(edge.target), edge.kind.value, edge.detail)


def _requirement_sort_key(requirement: Requirement) -> tuple[str, ...]:
    return (
        str(requirement.source),
        str(requirement.target),
        requirement.kind.value,
        requirement.detail,
    )


def _boundary_sort_key(boundary: UnknownBoundary) -> tuple[str, ...]:
    return (
        str(boundary.source),
        boundary.domain,
        boundary.reason,
        *(str(target) for target in boundary.targets),
    )


def _limitation_sort_key(limitation: Limitation) -> tuple[str, ...]:
    return (
        limitation.world.key if limitation.world else "",
        limitation.code,
        str(limitation.origin or ""),
        limitation.message,
    )
