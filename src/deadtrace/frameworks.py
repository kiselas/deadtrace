"""Built-in FastAPI and Dishka semantic capabilities.

The scanner recognizes documented source patterns without importing target
frameworks. Unsupported assembly weakens the affected world instead of being
treated as absence of execution.
"""

from __future__ import annotations

import ast
import posixpath
import sys
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum

from deadtrace.config import Config, WorldConfig
from deadtrace.core import (
    AssemblyState,
    EdgeKind,
    ExecutionEdge,
    Limitation,
    NodeId,
    NodeKind,
    Requirement,
    RootProvenance,
    SemanticGraph,
    UnknownBoundary,
    WorldId,
    WorldPlan,
)
from deadtrace.deployment import DeploymentReference
from deadtrace.entry_points import EntryPointIssue, ProjectEntryPoint
from deadtrace.python_frontend import (
    PythonModule,
    PythonProgram,
    PythonSymbol,
    _annotation_names,
    _dotted_name,
    _unstarred,
    call_arguments,
    declared_exports,
    flow_nodes,
    has_main_guard,
    is_fixture_decorator,
    is_function,
    is_test_path,
    keyword_argument,
    positional_arguments,
    simple_block_statements,
    single_string_literal,
    subscript_elements,
    subscript_items,
)
from deadtrace.timing import StageTimings


class FrameworkObjectKind(StrEnum):
    FASTAPI_APP = "fastapi_app"
    FASTAPI_ROUTER = "fastapi_router"
    DISHKA_CONTAINER = "dishka_container"


APPLICATION_CONSTRUCTORS = {
    "aiohttp.web.Application": "aiohttp",
    "bottle.Bottle": "bottle",
    "celery.Celery": "celery",
    "falcon.App": "falcon",
    "falcon.asgi.App": "falcon",
    "faststream.FastStream": "faststream",
    "faststream.app.FastStream": "faststream",
    "faststream.asgi.AsgiFastStream": "faststream",
    "faststream.asgi.app.AsgiFastStream": "faststream",
    "flask.Flask": "flask",
    "litestar.Litestar": "litestar",
    "quart.Quart": "quart",
    "sanic.Sanic": "sanic",
    "starlette.applications.Starlette": "starlette",
    "taskiq.TaskiqScheduler": "taskiq",
    "taskiq.scheduler.scheduler.TaskiqScheduler": "taskiq",
    "taskiq_faststream.StreamScheduler": "taskiq",
    "typer.Typer": "typer",
}
"""Application constructors of frameworks without a capability. The module or factory that
builds one is an execution root; handlers registered on the application by decorators are
protected by the decorator rule of ADR-0008. A project class deriving from one of them builds
an application as well, and an arq worker is a class with ``functions`` or ``cron_jobs`` that
the ``arq`` command reads (ADR-0022)."""
ARQ_WORKER_ATTRIBUTES = frozenset({"functions", "cron_jobs"})

_APPLICATION_PACKAGES = frozenset(name.partition(".")[0] for name in APPLICATION_CONSTRUCTORS)
DJANGO_APP_MODULES = ("apps", "models", "admin")
"""Modules of an installed application that Django imports when it starts."""
DJANGO_APP_PACKAGES = ("management.commands", "templatetags")
"""Packages of an installed application whose modules Django loads by name on demand."""
_NON_LIBRARY_DIRECTORIES = frozenset({"benchmarks", "docs", "examples"})
AUTO_ROOT = "<auto>"
"""The root of the placeholder world of a project in which no automatic root was found."""


@dataclass(slots=True)
class FrameworkObject:
    key: str
    module: str
    name: str
    kind: FrameworkObjectKind
    line: int
    dependencies: tuple[NodeId, ...] = ()
    dishka_route: bool = False
    provider_classes: tuple[NodeId, ...] = ()
    has_fastapi_provider: bool = False
    context_types: tuple[str, ...] = ()
    lifespan: NodeId | None = None


@dataclass(frozen=True, slots=True)
class RouteRegistration:
    owner: str
    endpoint: NodeId
    dependencies: tuple[NodeId, ...]
    dishka_demands: tuple[str, ...]
    schema_types: tuple[str, ...]
    explicitly_injected: bool
    path: str
    line: int


@dataclass(frozen=True, slots=True)
class RouterInclude:
    owner: str
    router: str
    dependencies: tuple[NodeId, ...]
    path: str
    line: int


@dataclass(frozen=True, slots=True)
class FrameworkHook:
    owner: str
    callback: NodeId
    kind: str
    path: str
    line: int


@dataclass(frozen=True, slots=True)
class ProviderBinding:
    provider_class: NodeId
    factory: NodeId
    provides: str
    dependencies: tuple[str, ...]
    scope: str
    path: str
    line: int


@dataclass(frozen=True, slots=True)
class ContextBinding:
    provider_class: NodeId
    provides: str
    scope: str
    override: bool
    path: str
    line: int


@dataclass(frozen=True, slots=True)
class ProviderAlias:
    provider_class: NodeId
    source: str
    provides: str
    path: str
    line: int


@dataclass(frozen=True, slots=True)
class FrameworkCapability:
    id: str
    revision: int
    status: str


@dataclass(slots=True)
class FrameworkModel:
    graph: SemanticGraph
    plans: tuple[WorldPlan, ...]
    objects: dict[str, FrameworkObject]
    routes: tuple[RouteRegistration, ...]
    hooks: tuple[FrameworkHook, ...]
    includes: tuple[RouterInclude, ...]
    bindings: tuple[ProviderBinding, ...]
    context_bindings: tuple[ContextBinding, ...]
    app_containers: dict[str, str]
    capabilities: tuple[FrameworkCapability, ...]
    unknown_includes: tuple[tuple[str, int], ...] = ()
    """``include_router`` calls whose application or router is not resolved: (path, line)."""
    escaping_routers: frozenset[str] = frozenset()
    """Routers referenced other than by their route decorators, so that any include may add them."""


@dataclass(slots=True)
class _BuildState:
    program: PythonProgram
    config: Config
    entry_points: tuple[ProjectEntryPoint, ...] = ()
    entry_point_issues: tuple[EntryPointIssue, ...] = ()
    deployment: tuple[DeploymentReference, ...] = ()
    objects: dict[str, FrameworkObject] = field(default_factory=dict)
    routes: list[RouteRegistration] = field(default_factory=list)
    hooks: list[FrameworkHook] = field(default_factory=list)
    includes: list[RouterInclude] = field(default_factory=list)
    handled_include_calls: set[int] = field(default_factory=set)
    """Identities of the ``include_router`` calls the direct patterns already modeled."""
    unknown_includes: list[tuple[str, int]] = field(default_factory=list)
    bindings: list[ProviderBinding] = field(default_factory=list)
    context_bindings: list[ContextBinding] = field(default_factory=list)
    provider_aliases: list[ProviderAlias] = field(default_factory=list)
    conditional_providers: set[NodeId] = field(default_factory=set)
    unsupported_provider_features: dict[NodeId, set[str]] = field(
        default_factory=lambda: defaultdict(set)
    )
    migration_callbacks: set[NodeId] = field(default_factory=set)
    migration_declarations: set[NodeId] = field(default_factory=set)
    unknown_migration_modules: set[str] = field(default_factory=set)
    applications: dict[str, tuple[str, str]] = field(default_factory=dict)
    """Applications of frameworks without a capability: key to (framework, root to run)."""
    application_names: dict[str, set[str]] = field(default_factory=dict)
    """Names of module-level application objects, per module."""
    auto_provenance: dict[tuple[str, str], tuple[str, str]] = field(default_factory=dict)
    """How automatic worlds found their roots: (scenario, root) to (kind, detail)."""
    app_factories: dict[NodeId, str] = field(default_factory=dict)
    factory_entry_callers: dict[str, set[NodeId]] = field(default_factory=dict)
    """Uncalled functions that call an application factory, by application key."""
    factory_app_locals: dict[str, tuple[NodeId, str]] = field(default_factory=dict)
    provider_instances: dict[str, NodeId] = field(default_factory=dict)
    app_containers: dict[str, str] = field(default_factory=dict)
    edges: list[ExecutionEdge] = field(default_factory=list)
    requirements: list[Requirement] = field(default_factory=list)
    boundaries: list[UnknownBoundary] = field(default_factory=list)
    pydantic_hooks: set[NodeId] = field(default_factory=set)
    """Validator, serializer, and schema hooks of project Pydantic models."""
    object_keys: dict[str, str] = field(default_factory=dict)
    """Object key by dotted ``module.name``; filled once ``_discover_objects`` has finished."""
    container_bindings: dict[str, _ContainerBindings] = field(default_factory=dict)
    """Bindings per container key; filled lazily during planning, after binding discovery."""
    routes_by_owner: dict[str, list[RouteRegistration]] = field(default_factory=dict)
    hooks_by_owner: dict[str, list[FrameworkHook]] = field(default_factory=dict)
    includes_by_owner: dict[str, list[RouterInclude]] = field(default_factory=dict)
    """Registrations grouped by owner in discovery order; filled when planning starts."""


@dataclass(frozen=True, slots=True)
class _ContainerBindings:
    """Bindings available in one container, keyed by the type they provide."""

    by_provides: dict[str, list[ProviderBinding]]
    context_by_provides: dict[str, list[ContextBinding]]


@dataclass(frozen=True, slots=True)
class _ModeledEscapes:
    """Callables each framework capability accounts for once discovery and planning are done."""

    background_tasks: dict[NodeId, set[NodeId]]
    depends: set[NodeId]
    lifespans: set[NodeId]
    context_types: set[NodeId]
    provided: set[NodeId]
    aliased: set[NodeId]
    registrations: set[NodeId]
    """Functions a modeled decorator registers: routes, hooks, and provider factories."""


def build_framework_model(
    program: PythonProgram,
    config: Config,
    *,
    entry_points: tuple[ProjectEntryPoint, ...] = (),
    entry_point_issues: tuple[EntryPointIssue, ...] = (),
    deployment: tuple[DeploymentReference, ...] = (),
    timings: StageTimings | None = None,
) -> FrameworkModel:
    """Apply built-in framework capabilities and construct isolated world plans."""

    timings = timings if timings is not None else StageTimings()
    state = _BuildState(
        program=program,
        config=config,
        entry_points=entry_points,
        entry_point_issues=entry_point_issues,
        deployment=deployment,
    )
    with timings.stage("frontend.frameworks_discover"):
        _discover_provider_bindings(state)
        _discover_objects(state)
        _discover_uncalled_fastapi_factories(state)
        _index_object_keys(state)
        _discover_factory_assembly(state)
        _discover_routes(state)
        _discover_includes_and_setup(state)
        _discover_indirect_includes(state)
        _discover_migration_contracts(state)
        _discover_application_factories(state)
        _discover_arq_workers(state)
        _discover_task_autodiscovery(state)
        _discover_django_applications(state)
        _discover_cli_commands(state)
        _connect_provider_dependencies(state)
        _connect_pydantic_models(state)
    with timings.stage("frontend.frameworks_plans"):
        plans = _build_world_plans(state)
    with timings.stage("frontend.frameworks_graph"):
        modeled = _modeled_escapes(state)
        frontend_boundaries = tuple(
            boundary
            for boundary in program.graph.boundaries
            if not _is_modeled_frontend_boundary(state, modeled, boundary)
        )
        graph = SemanticGraph(
            nodes=program.graph.nodes,
            edges=tuple(sorted(set((*program.graph.edges, *state.edges)), key=_edge_sort_key)),
            requirements=tuple(
                sorted(
                    set((*program.graph.requirements, *state.requirements)),
                    key=_requirement_sort_key,
                )
            ),
            boundaries=tuple(
                sorted(
                    set((*frontend_boundaries, *state.boundaries)),
                    key=_boundary_sort_key,
                )
            ),
        )
    timings.count("frameworks.edges", len(state.edges))
    timings.count("frameworks.requirements", len(state.requirements))
    timings.count("graph.requirements", len(graph.requirements))
    timings.count("graph.boundaries", len(graph.boundaries))
    return FrameworkModel(
        graph=graph,
        plans=plans,
        objects=state.objects,
        routes=tuple(sorted(state.routes, key=_route_sort_key)),
        hooks=tuple(sorted(state.hooks, key=_hook_sort_key)),
        includes=tuple(sorted(state.includes, key=_include_sort_key)),
        bindings=tuple(sorted(state.bindings, key=_binding_sort_key)),
        context_bindings=tuple(sorted(state.context_bindings, key=_context_binding_sort_key)),
        app_containers=dict(sorted(state.app_containers.items())),
        unknown_includes=tuple(sorted(set(state.unknown_includes))),
        escaping_routers=_escaping_routers(state),
        capabilities=(
            FrameworkCapability("python.direct-flow", 6, "modeled"),
            FrameworkCapability("fastapi.routes", 3, "modeled"),
            FrameworkCapability("fastapi.depends", 1, "modeled"),
            FrameworkCapability("dishka.fastapi", 1, "modeled"),
            FrameworkCapability("dishka.provider-method", 1, "modeled"),
            FrameworkCapability("dishka.class-provider", 1, "modeled"),
            FrameworkCapability("dishka.alias", 1, "modeled"),
            FrameworkCapability("dishka.from-context", 1, "modeled"),
            FrameworkCapability("dishka.conditional-activation", 1, "guarded"),
            FrameworkCapability("dishka.components-decorators", 1, "guarded"),
            FrameworkCapability("fastapi.lifecycle", 1, "modeled"),
            FrameworkCapability("fastapi.background-task", 1, "modeled"),
            FrameworkCapability("pydantic.hooks", 2, "modeled"),
            FrameworkCapability("django.migrations-runpython", 2, "modeled"),
            FrameworkCapability("python.project-entry-points", 2, "modeled"),
            FrameworkCapability("python.script-roots", 1, "modeled"),
            FrameworkCapability("python.library-roots", 1, "modeled"),
            FrameworkCapability("frameworks.application-roots", 1, "guarded"),
            FrameworkCapability("celery.autodiscover-tasks", 1, "guarded"),
            FrameworkCapability("django.installed-apps", 2, "modeled"),
            FrameworkCapability("alembic.migrations", 1, "modeled"),
            FrameworkCapability("cli.commands", 1, "modeled"),
            # The capability set describes the method, so it holds whether or not tests exist.
            FrameworkCapability("pytest.fixtures", 2, "modeled"),
            FrameworkCapability("deployment.commands", 1, "modeled"),
        ),
    )


def _modeled_escapes(state: _BuildState) -> _ModeledEscapes:
    background_tasks: defaultdict[NodeId, set[NodeId]] = defaultdict(set)
    for edge in state.edges:
        if edge.detail == "FastAPI BackgroundTasks.add_task callback":
            background_tasks[edge.source].add(edge.target)
    index = state.program.index
    return _ModeledEscapes(
        background_tasks=dict(background_tasks),
        depends={
            *(dependency for obj in state.objects.values() for dependency in obj.dependencies),
            *(dependency for route in state.routes for dependency in route.dependencies),
            *(dependency for include in state.includes for dependency in include.dependencies),
        },
        lifespans={obj.lifespan for obj in state.objects.values() if obj.lifespan is not None},
        context_types={
            symbol.id
            for binding in state.context_bindings
            for symbol in index.named(binding.provides)
            if symbol.kind is NodeKind.CLASS
        },
        provided={binding.factory for binding in state.bindings},
        aliased={
            symbol.id
            for alias in state.provider_aliases
            for name in {alias.source, alias.provides}
            for symbol in index.named(name)
        },
        registrations={
            *(route.endpoint for route in state.routes),
            *(hook.callback for hook in state.hooks),
            *(binding.factory for binding in state.bindings),
            *state.pydantic_hooks,
        },
    )


def _is_modeled_frontend_boundary(
    state: _BuildState, modeled: _ModeledEscapes, boundary: UnknownBoundary
) -> bool:
    """Return whether a framework capability fully accounts for an escaped callable."""

    targets = set(boundary.targets)
    if boundary.domain == "decorator_registration":
        return bool(targets) and targets <= modeled.registrations
    if boundary.domain == "escaped_class":
        # Judged by the class it names: the consumer's model accounts for the class or not.
        targets = {
            target
            for target in targets
            if (symbol := state.program.symbols.get(target)) is not None
            and symbol.kind is NodeKind.CLASS
        }
    elif boundary.domain != "escaped_callable":
        return False
    if "add_task" in boundary.reason:
        return bool(targets) and targets <= modeled.background_tasks.get(boundary.source, set())
    if boundary.reason.endswith("consumer fastapi.Depends"):
        return bool(targets) and targets <= modeled.depends
    if boundary.reason.endswith("consumer fastapi.FastAPI"):
        return bool(targets) and targets <= modeled.lifespans
    if boundary.reason.endswith("consumer dishka.from_context"):
        return bool(targets) and targets <= modeled.context_types
    if boundary.reason.endswith("consumer dishka.provide"):
        return bool(targets) and targets <= modeled.provided
    if boundary.reason.endswith("consumer dishka.alias"):
        return bool(targets) and targets <= modeled.aliased
    if boundary.reason.endswith("consumer django.db.migrations.RunPython"):
        return bool(targets) and targets <= state.migration_callbacks
    return False


def _discover_provider_bindings(state: _BuildState) -> None:
    provider_classes = {
        symbol.id: symbol
        for symbol in state.program.symbols.values()
        if symbol.kind is NodeKind.CLASS and _is_provider_class(state.program, symbol)
    }
    for provider in provider_classes.values():
        module = state.program.modules[provider.module]
        assert isinstance(provider.node, ast.ClassDef)
        if _provider_class_has_condition(module, provider.node):
            state.conditional_providers.add(provider.id)
        if _provider_class_has_component(module, provider.node):
            state.unsupported_provider_features[provider.id].add("provider component")
        for small in simple_block_statements(module, provider.node):
            if not (
                isinstance(small, ast.Assign)
                and len(small.targets) == 1
                and isinstance(small.targets[0], ast.Name)
                and isinstance(small.value, ast.Call)
            ):
                continue
            operation = _expanded_name(module, small.value.func)
            if operation in {"dishka.decorate", "dishka.provide_all"}:
                state.unsupported_provider_features[provider.id].add(operation)
                continue
            if operation == "dishka.provide":
                source_expression = _call_argument(small.value, "source", 0)
                source = (
                    state.program.resolve_symbol(_expanded_name(module, source_expression))
                    if source_expression is not None
                    else None
                )
                if source is None or source.kind is not NodeKind.CLASS:
                    continue
                provides_expression = _keyword_expression(small.value, "provides")
                provides = (
                    _project_or_external_expression_name(state.program, module, provides_expression)
                    if provides_expression is not None
                    else f"{source.module}.{source.qualified_name}"
                )
                if provides is None:
                    continue
                state.bindings.append(
                    ProviderBinding(
                        provider_class=provider.id,
                        factory=source.id,
                        provides=provides,
                        dependencies=_constructor_dependencies(state.program, source),
                        scope=(
                            _decorator_keyword_name(module, small.value, "scope") or "inherited"
                        ),
                        path=provider.path,
                        line=provider.line,
                    )
                )
                constructor = _constructor_symbol(state.program, source)
                if constructor is not None:
                    state.edges.append(
                        ExecutionEdge(
                            source.id,
                            constructor.id,
                            EdgeKind.CONSTRUCT,
                            f"Dishka constructs {source.qualified_name}",
                        )
                    )
                continue
            if operation == "dishka.alias":
                source_expression = _call_argument(small.value, "source", 0)
                provides_expression = _keyword_expression(small.value, "provides")
                source_name = (
                    _project_or_external_expression_name(state.program, module, source_expression)
                    if source_expression is not None
                    else None
                )
                provides = (
                    _project_or_external_expression_name(state.program, module, provides_expression)
                    if provides_expression is not None
                    else None
                )
                if source_name is not None and provides is not None:
                    state.provider_aliases.append(
                        ProviderAlias(
                            provider.id,
                            source_name,
                            provides,
                            provider.path,
                            provider.line,
                        )
                    )
                continue
            if operation != "dishka.from_context":
                continue
            provides_expression = _keyword_expression(small.value, "provides")
            if provides_expression is None:
                continue
            provides = _project_or_external_expression_name(
                state.program, module, provides_expression
            )
            if provides is None:
                continue
            scope = _decorator_keyword_name(module, small.value, "scope") or "inherited"
            override_expression = _keyword_expression(small.value, "override")
            override = _dotted_name(override_expression) == "True"
            state.context_bindings.append(
                ContextBinding(
                    provider_class=provider.id,
                    provides=provides,
                    scope=scope,
                    override=override,
                    path=provider.path,
                    line=provider.line,
                )
            )
        for symbol in module.symbols:
            if symbol.owner != provider.id or not is_function(symbol):
                continue
            if _provider_member_has_condition(module, symbol):
                state.conditional_providers.add(provider.id)
            if _find_decorator(module, symbol, {"dishka.decorate"}) is not None:
                state.unsupported_provider_features[provider.id].add("dishka.decorate")
            provide_decorator = _find_decorator(module, symbol, {"dishka.provide"})
            if provide_decorator is None:
                continue
            provides = _decorator_keyword_type(
                state.program, module, provide_decorator, "provides"
            ) or _annotation_project_or_external_name(module, symbol.return_annotation)
            if provides is None:
                continue
            dependencies = tuple(
                target
                for parameter in symbol.parameters
                if parameter.name not in {"self", "cls"} and parameter.annotation is not None
                for target in [_annotation_project_or_external_name(module, parameter.annotation)]
                if target is not None
            )
            scope = _decorator_keyword_name(module, provide_decorator, "scope") or "inherited"
            state.bindings.append(
                ProviderBinding(
                    provider_class=provider.id,
                    factory=symbol.id,
                    provides=provides,
                    dependencies=dependencies,
                    scope=scope,
                    path=symbol.path,
                    line=symbol.line,
                )
            )
    concrete_bindings = tuple(state.bindings)
    for alias in state.provider_aliases:
        sources = [
            binding
            for binding in concrete_bindings
            if binding.provider_class == alias.provider_class and binding.provides == alias.source
        ]
        if len(sources) != 1:
            continue
        source_binding = sources[0]
        state.bindings.append(
            ProviderBinding(
                provider_class=alias.provider_class,
                factory=source_binding.factory,
                provides=alias.provides,
                dependencies=source_binding.dependencies,
                scope=source_binding.scope,
                path=alias.path,
                line=alias.line,
            )
        )


def _discover_objects(state: _BuildState) -> None:
    for module in state.program.modules.values():
        for name, value, line in _top_level_assignments(module):
            if not isinstance(value, ast.Call):
                continue
            function_name = _expanded_name(module, value.func)
            key = f"{module.name}:{name}"
            if function_name in {"fastapi.FastAPI", "fastapi.applications.FastAPI"}:
                lifespan_expression = _keyword_expression(value, "lifespan")
                lifespan_symbol = (
                    state.program.resolve_symbol(_expanded_name(module, lifespan_expression))
                    if lifespan_expression is not None
                    else None
                )
                state.objects[key] = FrameworkObject(
                    key=key,
                    module=module.name,
                    name=name,
                    kind=FrameworkObjectKind.FASTAPI_APP,
                    line=line,
                    dependencies=_dependencies_from_call(state.program, module, value),
                    lifespan=lifespan_symbol.id if lifespan_symbol is not None else None,
                )
            elif function_name in {"fastapi.APIRouter", "fastapi.routing.APIRouter"}:
                route_class = _keyword_expression(value, "route_class")
                state.objects[key] = FrameworkObject(
                    key=key,
                    module=module.name,
                    name=name,
                    kind=FrameworkObjectKind.FASTAPI_ROUTER,
                    line=line,
                    dependencies=_dependencies_from_call(state.program, module, value),
                    dishka_route=(
                        route_class is not None
                        and _expanded_name(module, route_class).endswith("DishkaRoute")
                    ),
                )
            elif function_name in {"dishka.make_async_container", "dishka.make_container"}:
                provider_ids: list[NodeId] = []
                has_fastapi_provider = False
                for argument in call_arguments(value):
                    if argument.keyword is not None:
                        continue
                    provider = _provider_class_from_expression(state, module, argument.value)
                    if provider is not None:
                        provider_ids.append(provider.id)
                        if isinstance(argument.value, ast.Call):
                            if _keyword_expression(argument.value, "component") is not None:
                                state.unsupported_provider_features[provider.id].add(
                                    "provider component constructor"
                                )
                            if _keyword_expression(argument.value, "when") is not None:
                                state.conditional_providers.add(provider.id)
                    elif isinstance(argument.value, ast.Call) and _expanded_name(
                        module, argument.value.func
                    ).endswith("FastapiProvider"):
                        has_fastapi_provider = True
                state.objects[key] = FrameworkObject(
                    key=key,
                    module=module.name,
                    name=name,
                    kind=FrameworkObjectKind.DISHKA_CONTAINER,
                    line=line,
                    provider_classes=tuple(sorted(set(provider_ids))),
                    has_fastapi_provider=has_fastapi_provider,
                    context_types=_context_types_from_call(state.program, module, value),
                )
                for provider_id in sorted(set(provider_ids)):
                    state.requirements.append(
                        Requirement(
                            source=module.node_id,
                            target=provider_id,
                            kind=EdgeKind.DEPENDENCY,
                            detail=f"provider registered in {key}",
                        )
                    )
                    for binding in state.bindings:
                        if binding.provider_class == provider_id:
                            state.requirements.append(
                                Requirement(
                                    source=module.node_id,
                                    target=binding.factory,
                                    kind=EdgeKind.DEPENDENCY,
                                    detail=f"binding registered for {binding.provides}",
                                )
                            )
                    for alias in state.provider_aliases:
                        if alias.provider_class != provider_id:
                            continue
                        for type_name in (alias.source, alias.provides):
                            target = state.program.resolve_symbol(type_name)
                            if target is not None:
                                state.requirements.append(
                                    Requirement(
                                        source=module.node_id,
                                        target=target.id,
                                        kind=EdgeKind.DEPENDENCY,
                                        detail=f"Dishka alias retains {type_name}",
                                    )
                                )
            elif (framework := _application_framework(state, module, value.func)) is not None:
                state.applications[key] = (framework, module.name)
                state.application_names.setdefault(module.name, set()).add(name)
            else:
                provider = _provider_class_from_expression(state, module, value)
                if provider is not None:
                    state.provider_instances[key] = provider.id
                    continue
                factory = state.program.resolve_symbol(function_name)
                if factory is None or not is_function(factory):
                    continue
                factory_app = _fastapi_factory_app(state, factory)
                if factory_app is None:
                    continue
                local_name, constructor = factory_app
                factory_module = state.program.modules[factory.module]
                lifespan_expression = _keyword_expression(constructor, "lifespan")
                lifespan_symbol = (
                    state.program.resolve_symbol(
                        _expanded_name(factory_module, lifespan_expression)
                    )
                    if lifespan_expression is not None
                    else None
                )
                state.objects[key] = FrameworkObject(
                    key=key,
                    module=module.name,
                    name=name,
                    kind=FrameworkObjectKind.FASTAPI_APP,
                    line=line,
                    dependencies=_dependencies_from_call(
                        state.program, factory_module, constructor
                    ),
                    lifespan=lifespan_symbol.id if lifespan_symbol is not None else None,
                )
                state.app_factories[factory.id] = key
                state.factory_app_locals[key] = (factory.id, local_name)


def _discover_uncalled_fastapi_factories(state: _BuildState) -> None:
    """A top-level ``create_app`` no module calls is an application, as ``--factory`` runs it."""

    for module in state.program.modules.values():
        if is_test_path(module.path) or not any(
            binding.target.partition(".")[0] == "fastapi" for binding in module.imports.values()
        ):
            continue  # a test that builds an application is not one a server runs
        for factory in module.symbols:
            if (
                factory.owner is not None
                or not is_function(factory)
                or factory.id in state.app_factories
            ):
                continue
            factory_app = _fastapi_factory_app(state, factory, wrapped=True)
            if factory_app is None:
                continue
            local_name, constructor = factory_app
            key = f"{module.name}:{factory.qualified_name}"
            lifespan_expression = _keyword_expression(constructor, "lifespan")
            lifespan_symbol = (
                state.program.resolve_symbol(_expanded_name(module, lifespan_expression))
                if lifespan_expression is not None
                else None
            )
            state.objects[key] = FrameworkObject(
                key=key,
                module=module.name,
                name=factory.name,
                kind=FrameworkObjectKind.FASTAPI_APP,
                line=factory.line,
                dependencies=_dependencies_from_call(state.program, module, constructor),
                lifespan=lifespan_symbol.id if lifespan_symbol is not None else None,
            )
            state.app_factories[factory.id] = key
            state.factory_app_locals[key] = (factory.id, local_name)
    _discover_factory_entry_callers(state)


def _discover_factory_entry_callers(state: _BuildState) -> None:
    """Uncalled functions that call an application factory: a server runs them by name.

    ``uvicorn app.main:create_default --factory`` runs ``create_default``, which calls the
    factory that builds the application. No project code calls it, so it is a root of the
    application's world with the factory (ADR-0019).
    """

    factories = {factory_id: key for key, (factory_id, _local) in state.factory_app_locals.items()}
    if not factories:
        return
    sites = _function_call_sites(state)
    for factory_id, key in factories.items():
        for _module, _call, caller in sites.get(factory_id, ()):
            if (
                caller is not None
                and caller.owner is None
                and caller.id not in sites
                and caller.id not in state.app_factories
            ):
                state.factory_entry_callers.setdefault(key, set()).add(caller.id)


def _discover_factory_assembly(state: _BuildState) -> None:
    """Model a bounded create_app pattern without executing the factory."""

    for app_key, (factory_id, local_app_name) in state.factory_app_locals.items():
        _connect_factory_assembly(state, app_key, factory_id, local_app_name)


def _connect_factory_assembly(
    state: _BuildState,
    app_key: str,
    factory_id: NodeId,
    local_app_name: str,
) -> None:
    factory = state.program.symbols[factory_id]
    module = state.program.modules[factory.module]
    assert not isinstance(factory.node, ast.ClassDef)

    def visit_call(call: ast.Call) -> None:
        if (
            isinstance(call.func, ast.Attribute)
            and isinstance(call.func.value, ast.Name)
            and call.func.value.id == local_app_name
            and call.func.attr == "include_router"
        ):
            router = _first_argument_object_key(state, module, call)
            if (
                router is not None
                and state.objects[router].kind is FrameworkObjectKind.FASTAPI_ROUTER
            ):
                state.handled_include_calls.add(id(call))
                state.includes.append(
                    RouterInclude(
                        owner=app_key,
                        router=router,
                        dependencies=_dependencies_from_call(state.program, module, call),
                        path=module.path,
                        line=factory.line,
                    )
                )
            return
        if _expanded_name(module, call.func) not in {
            "dishka.integrations.fastapi.setup_dishka",
            "dishka.integrations.fastapi.setup_dishka.setup_dishka",
        }:
            return
        app_expression = _call_argument(call, "app", 1)
        if not (isinstance(app_expression, ast.Name) and app_expression.id == local_app_name):
            return
        container_expression = _call_argument(call, "container", 0)
        container = (
            _object_key(state, module, container_expression)
            if container_expression is not None
            else None
        )
        if (
            container is not None
            and state.objects[container].kind is FrameworkObjectKind.DISHKA_CONTAINER
        ):
            state.app_containers[app_key] = container

    for node in flow_nodes(factory.node.body):
        if isinstance(node, ast.Call):
            visit_call(node)


def _discover_routes(state: _BuildState) -> None:
    for module in state.program.modules.values():
        for symbol in module.symbols:
            if not is_function(symbol):
                continue
            explicitly_injected = (
                _find_decorator(
                    module,
                    symbol,
                    {
                        "dishka.integrations.fastapi.inject",
                        "dishka.integrations.fastapi.inject_sync",
                    },
                )
                is not None
            )
            parameter_dependencies = _parameter_dependencies(state.program, module, symbol)
            for dependency in parameter_dependencies:
                state.edges.append(
                    ExecutionEdge(
                        symbol.id,
                        dependency,
                        EdgeKind.DEPENDENCY,
                        "FastAPI parameter dependency",
                    )
                )
            for expression in symbol.decorators:
                if not isinstance(expression, ast.Call) or not isinstance(
                    expression.func, ast.Attribute
                ):
                    continue
                if expression.func.attr not in {
                    "get",
                    "post",
                    "put",
                    "patch",
                    "delete",
                    "options",
                    "head",
                    "trace",
                    "api_route",
                    "websocket",
                }:
                    if expression.func.attr not in {
                        "on_event",
                        "exception_handler",
                        "middleware",
                    }:
                        continue
                    owner = _object_key(state, module, expression.func.value)
                    if (
                        owner is not None
                        and state.objects[owner].kind is FrameworkObjectKind.FASTAPI_APP
                    ):
                        state.hooks.append(
                            FrameworkHook(
                                owner=owner,
                                callback=symbol.id,
                                kind=expression.func.attr,
                                path=symbol.path,
                                line=symbol.line,
                            )
                        )
                        state.requirements.append(
                            Requirement(
                                source=module.node_id,
                                target=symbol.id,
                                kind=EdgeKind.LIFECYCLE,
                                detail=f"FastAPI {expression.func.attr} hook on {owner}",
                            )
                        )
                    continue
                owner = _object_key(state, module, expression.func.value)
                if owner is None or state.objects[owner].kind not in {
                    FrameworkObjectKind.FASTAPI_APP,
                    FrameworkObjectKind.FASTAPI_ROUTER,
                }:
                    continue
                dependencies = tuple(
                    sorted(
                        set(
                            (
                                *parameter_dependencies,
                                *_dependencies_from_call(state.program, module, expression),
                            )
                        )
                    )
                )
                demands = _dishka_demands(module, symbol)
                schema_types = _pydantic_schema_types(state.program, module, symbol)
                state.routes.append(
                    RouteRegistration(
                        owner=owner,
                        endpoint=symbol.id,
                        dependencies=dependencies,
                        dishka_demands=demands,
                        schema_types=schema_types,
                        explicitly_injected=explicitly_injected,
                        path=symbol.path,
                        line=symbol.line,
                    )
                )
                for callback in _background_callbacks(state.program, module, symbol):
                    state.edges.append(
                        ExecutionEdge(
                            symbol.id,
                            callback,
                            EdgeKind.CALLBACK,
                            "FastAPI BackgroundTasks.add_task callback",
                        )
                    )
                state.requirements.append(
                    Requirement(
                        source=module.node_id,
                        target=symbol.id,
                        kind=EdgeKind.FRAMEWORK,
                        detail=f"route registered on {owner}",
                    )
                )


def _discover_includes_and_setup(state: _BuildState) -> None:
    for module in state.program.modules.values():
        for call, line in _top_level_calls(module):
            if isinstance(call.func, ast.Attribute) and call.func.attr == "include_router":
                owner = _object_key(state, module, call.func.value)
                router = _first_argument_object_key(state, module, call)
                if (
                    owner is not None
                    and router is not None
                    and state.objects[owner].kind
                    in {FrameworkObjectKind.FASTAPI_APP, FrameworkObjectKind.FASTAPI_ROUTER}
                    and state.objects[router].kind is FrameworkObjectKind.FASTAPI_ROUTER
                ):
                    state.handled_include_calls.add(id(call))
                    state.includes.append(
                        RouterInclude(
                            owner=owner,
                            router=router,
                            dependencies=_dependencies_from_call(state.program, module, call),
                            path=module.path,
                            line=line,
                        )
                    )
            elif _expanded_name(module, call.func) in {
                "dishka.integrations.fastapi.setup_dishka",
                "dishka.integrations.fastapi.setup_dishka.setup_dishka",
            }:
                container_expression = _call_argument(call, "container", 0)
                app_expression = _call_argument(call, "app", 1)
                container = (
                    _object_key(state, module, container_expression)
                    if container_expression is not None
                    else None
                )
                app = (
                    _object_key(state, module, app_expression)
                    if app_expression is not None
                    else None
                )
                if (
                    app is not None
                    and container is not None
                    and state.objects[app].kind is FrameworkObjectKind.FASTAPI_APP
                    and state.objects[container].kind is FrameworkObjectKind.DISHKA_CONTAINER
                ):
                    state.app_containers[app] = container


type _CallSite = tuple[PythonModule, ast.Call, PythonSymbol | None]
"""A call, the module it is in, and the function whose body holds it (``None`` at top level)."""

_INDIRECT_DEPTH = 3
"""How many helper calls an application may be passed through before an include is unknown."""


def _discover_indirect_includes(state: _BuildState) -> None:
    """Router includes that the direct patterns miss (ADR-0017).

    An ``include_router`` call in a nested block, in a helper function that receives the
    application as a parameter, or over a ``for`` loop through a literal list of routers is
    modeled when every application it may run on and every router it may include resolve. Any
    other ``include_router`` call is recorded as unknown, so that no router it may include is
    reported as unpublished.
    """

    sites: dict[NodeId, list[_CallSite]] | None = None
    for module, call, scope in _include_calls(state):
        if id(call) in state.handled_include_calls:
            continue
        assert isinstance(call.func, ast.Attribute)
        receiver = call.func.value
        if sites is None and _needs_call_sites(state, module, scope, receiver):
            sites = _function_call_sites(state)
        owners = _include_owners(state, module, scope, receiver, sites or {}, _INDIRECT_DEPTH)
        router_expression = _call_argument(call, "router", 0)
        routers = (
            _router_values(state, module, scope, router_expression)
            if router_expression is not None
            else None
        )
        if not owners or not routers:
            state.unknown_includes.append((module.path, call.lineno))
            continue
        state.handled_include_calls.add(id(call))
        dependencies = _dependencies_from_call(state.program, module, call)
        for owner in sorted(owners):
            for router in sorted(routers):
                state.includes.append(
                    RouterInclude(
                        owner=owner,
                        router=router,
                        dependencies=dependencies,
                        path=module.path,
                        line=call.lineno,
                    )
                )


def _include_calls(state: _BuildState) -> Iterator[_CallSite]:
    for module in state.program.modules.values():
        if "include_router" not in module.unit.source:
            continue
        scopes: list[tuple[PythonSymbol | None, list[ast.stmt]]] = [(None, module.tree.body)]
        scopes.extend(
            (symbol, symbol.node.body) for symbol in module.symbols if is_function(symbol)
        )
        for scope, body in scopes:
            for node in flow_nodes(body):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "include_router"
                ):
                    yield module, node, scope


def _needs_call_sites(
    state: _BuildState, module: PythonModule, scope: PythonSymbol | None, receiver: ast.expr
) -> bool:
    return (
        scope is not None
        and isinstance(receiver, ast.Name)
        and _object_key(state, module, receiver) is None
        and any(parameter.name == receiver.id for parameter in scope.parameters)
    )


def _function_call_sites(state: _BuildState) -> dict[NodeId, list[_CallSite]]:
    """Every call of a project function, by the function it calls; built once when needed."""

    program = state.program
    sites: dict[NodeId, list[_CallSite]] = defaultdict(list)
    for module in program.modules.values():
        scopes: list[tuple[PythonSymbol | None, list[ast.stmt]]] = [(None, module.tree.body)]
        scopes.extend(
            (symbol, symbol.node.body) for symbol in module.symbols if is_function(symbol)
        )
        for scope, body in scopes:
            for node in flow_nodes(body):
                if not isinstance(node, ast.Call):
                    continue
                name = _expanded_name(module, node.func)
                target = program.resolve_symbol(name) if name else None
                if target is not None and is_function(target):
                    sites[target.id].append((module, node, scope))
    return sites


def _include_owners(
    state: _BuildState,
    module: PythonModule,
    scope: PythonSymbol | None,
    expression: ast.expr,
    sites: dict[NodeId, list[_CallSite]],
    depth: int,
) -> set[str] | None:
    """The applications and routers an ``include_router`` receiver may be, or ``None``."""

    key = _object_key(state, module, expression)
    if key is not None:
        kind = state.objects[key].kind
        routable = {FrameworkObjectKind.FASTAPI_APP, FrameworkObjectKind.FASTAPI_ROUTER}
        return {key} if kind in routable else None
    if scope is None or not isinstance(expression, ast.Name):
        return None
    factory_app = state.app_factories.get(scope.id)
    if factory_app is not None and state.factory_app_locals[factory_app][1] == expression.id:
        return {factory_app}
    if depth == 0 or scope.owner is not None:
        return None
    names = [parameter.name for parameter in scope.parameters]
    if expression.id not in names:
        return None
    position = names.index(expression.id)
    callers = sites.get(scope.id, [])
    if not callers:
        return None
    owners: set[str] = set()
    for caller_module, call, caller_scope in callers:
        argument = _call_argument(call, expression.id, position)
        if argument is None:
            return None
        found = _include_owners(state, caller_module, caller_scope, argument, sites, depth - 1)
        if found is None:
            return None
        owners.update(found)
    return owners


def _router_values(
    state: _BuildState,
    module: PythonModule,
    scope: PythonSymbol | None,
    expression: ast.expr,
) -> set[str] | None:
    """The routers an ``include_router`` argument may be, or ``None`` when that is unknown."""

    if isinstance(expression, ast.Name):
        body = scope.node.body if scope is not None else module.tree.body
        loops = [
            node
            for node in flow_nodes(body)
            if isinstance(node, (ast.For, ast.AsyncFor))
            and isinstance(node.target, ast.Name)
            and node.target.id == expression.id
            and any(child is expression for child in ast.walk(node))
        ]
        if loops:
            innermost = max(loops, key=lambda node: (node.lineno, node.col_offset))
            return _router_list(state, module, innermost.iter, _INDIRECT_DEPTH)
    key = _object_key(state, module, expression)
    if key is None:
        return None
    return {key} if state.objects[key].kind is FrameworkObjectKind.FASTAPI_ROUTER else None


def _router_list(
    state: _BuildState, module: PythonModule, expression: ast.expr, depth: int
) -> set[str] | None:
    """The routers of a literal list or tuple, of a concatenation, or of a name bound to one."""

    if isinstance(expression, (ast.List, ast.Tuple)):
        routers: set[str] = set()
        for item in expression.elts:
            found = (
                _router_list(state, module, item.value, depth)
                if isinstance(item, ast.Starred)
                else _router_values(state, module, None, item)
            )
            if found is None:
                return None
            routers.update(found)
        return routers
    if isinstance(expression, ast.BinOp) and isinstance(expression.op, ast.Add):
        left = _router_list(state, module, expression.left, depth)
        right = _router_list(state, module, expression.right, depth)
        return left | right if left is not None and right is not None else None
    if depth == 0 or not isinstance(expression, (ast.Name, ast.Attribute)):
        return None
    module_name, _, name = _expanded_name(module, expression).rpartition(".")
    target_module = state.program.modules.get(module_name)
    if target_module is None:
        return None
    value = _single_module_assignment(target_module, name)
    return _router_list(state, target_module, value, depth - 1) if value is not None else None


def _single_module_assignment(module: PythonModule, name: str) -> ast.expr | None:
    """The value of the one top-level assignment to ``name``, if the module never changes it."""

    values: list[ast.expr] = []
    for node in ast.walk(module.tree):
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
                values.append(node.value)
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            if isinstance(node.target, ast.Name) and node.target.id == name:
                values.append(node.value)
        elif isinstance(node, ast.AugAssign):
            if isinstance(node.target, ast.Name) and node.target.id == name:
                return None
        elif (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == name
            and node.attr in {"append", "extend", "insert", "__iadd__"}
        ):
            return None
    if len(values) != 1 or not any(
        isinstance(statement, (ast.Assign, ast.AnnAssign)) and statement.value is values[0]
        for statement in module.tree.body
    ):
        return None
    return values[0]


def _escaping_routers(state: _BuildState) -> frozenset[str]:
    """Routers that code refers to other than through their own route decorators.

    Only these may be passed to an ``include_router`` call that is not resolved; a router that
    no import names and its module uses only to decorate routes cannot be.
    """

    routers = {
        key: obj
        for key, obj in state.objects.items()
        if obj.kind is FrameworkObjectKind.FASTAPI_ROUTER
    }
    if not routers:
        return frozenset()
    imported = {
        binding.target
        for module in state.program.modules.values()
        for binding in module.imports.values()
    }
    escaping: set[str] = set()
    for key, obj in routers.items():
        if f"{obj.module}.{obj.name}" in imported:
            escaping.add(key)
            continue
        module = state.program.modules[obj.module]
        loads = sum(
            1
            for node in ast.walk(module.tree)
            if isinstance(node, ast.Name) and node.id == obj.name and isinstance(node.ctx, ast.Load)
        )
        decorations = sum(
            1
            for symbol in module.symbols
            for expression in symbol.decorators
            if isinstance(expression, ast.Call)
            and isinstance(expression.func, ast.Attribute)
            and isinstance(expression.func.value, ast.Name)
            and expression.func.value.id == obj.name
        )
        if loads > decorations:
            escaping.add(key)
    return frozenset(escaping)


def _discover_migration_contracts(state: _BuildState) -> None:
    """Retain RunPython callbacks as external historical execution contracts."""

    packages = _django_migration_packages(state)
    for module in state.program.modules.values():
        path_parts = module.path.replace("\\", "/").split("/")
        if "migrations" not in path_parts and not module.name.startswith(packages):
            continue
        _discover_module_migration_contracts(state, module)
    _discover_alembic_contracts(state)


def _django_migration_packages(state: _BuildState) -> tuple[str, ...]:
    """Packages that ``MIGRATION_MODULES`` settings name, as ``"pkg."`` prefixes."""

    packages: set[str] = set()
    for module in state.program.modules.values():
        for statement in module.tree.body:
            if not (
                isinstance(statement, ast.Assign)
                and any(
                    isinstance(target, ast.Name) and target.id == "MIGRATION_MODULES"
                    for target in statement.targets
                )
                and isinstance(statement.value, ast.Dict)
            ):
                continue
            for value in statement.value.values:
                package = single_string_literal(value, module.text)
                if package:
                    packages.add(f"{package}.")
    return tuple(sorted(packages))


def _discover_alembic_contracts(state: _BuildState) -> None:
    """Alembic runs its environment script and the revision functions of its scripts.

    An environment is a module named ``env`` that imports ``alembic``; Alembic executes it by
    path. It calls ``upgrade`` and ``downgrade`` functions, and their ``*_<name>`` variants of
    multi-database templates, in the modules of the ``versions`` directory beside it. They are
    external execution contracts like Django's historical migrations (ADR-0017).
    """

    for module in state.program.modules.values():
        directory, _, file_name = module.path.rpartition("/")
        if file_name != "env.py" or not any(
            binding.target == "alembic" or binding.target.startswith("alembic.")
            for binding in module.imports.values()
        ):
            continue
        state.migration_declarations.add(module.node_id)
        prefix = f"{directory}/versions/" if directory else "versions/"
        for candidate in state.program.modules.values():
            if not candidate.path.startswith(prefix):
                continue
            state.migration_declarations.add(candidate.node_id)
            state.migration_callbacks.update(
                symbol.id
                for symbol in candidate.symbols
                if symbol.owner is None
                and is_function(symbol)
                and (
                    symbol.name in {"upgrade", "downgrade"}
                    or symbol.name.startswith(("upgrade_", "downgrade_"))
                )
            )


def _discover_module_migration_contracts(state: _BuildState, module: PythonModule) -> None:
    for node in ast.walk(module.tree):
        if isinstance(node, ast.ClassDef):
            _record_migration_declaration(state, module, node)
        elif isinstance(node, ast.Call):
            _record_migration_callbacks(state, module, node)


def _record_migration_declaration(
    state: _BuildState, module: PythonModule, node: ast.ClassDef
) -> None:
    if not any(
        _expanded_name(module, _unstarred(base)).endswith("migrations.Migration")
        for base in node.bases
    ):
        return
    declaration = state.program.resolve_symbol(f"{module.name}.{node.name}")
    if declaration is None:
        state.unknown_migration_modules.add(module.name)
    else:
        state.migration_declarations.add(declaration.id)


def _record_migration_callbacks(state: _BuildState, module: PythonModule, call: ast.Call) -> None:
    if not _expanded_name(module, call.func).endswith("migrations.RunPython"):
        return
    positional = positional_arguments(call)[:2]
    expressions = [
        *positional,
        *(
            expression
            for name in ("code", "reverse_code")[len(positional) :]
            if (expression := keyword_argument(call, name)) is not None
        ),
    ]
    if not expressions:
        state.unknown_migration_modules.add(module.name)
        return
    for expression in expressions:
        expanded = _expanded_name(module, expression)
        if expanded.endswith("RunPython.noop"):
            continue
        callback = state.program.resolve_symbol(expanded)
        if callback is None:
            state.unknown_migration_modules.add(module.name)
        else:
            state.migration_callbacks.add(callback.id)


def _connect_provider_dependencies(state: _BuildState) -> None:
    by_provider: defaultdict[NodeId, list[ProviderBinding]] = defaultdict(list)
    for binding in state.bindings:
        by_provider[binding.provider_class].append(binding)
    for container in state.objects.values():
        if container.kind is not FrameworkObjectKind.DISHKA_CONTAINER:
            continue
        bindings = [
            binding
            for provider in container.provider_classes
            for binding in by_provider.get(provider, ())
        ]
        by_type: defaultdict[str, list[ProviderBinding]] = defaultdict(list)
        for binding in bindings:
            by_type[binding.provides].append(binding)
        for binding in bindings:
            for dependency in binding.dependencies:
                candidates = by_type.get(dependency, ())
                if len(candidates) == 1:
                    state.edges.append(
                        ExecutionEdge(
                            binding.factory,
                            candidates[0].factory,
                            EdgeKind.DEPENDENCY,
                            f"Dishka resolves {dependency}",
                        )
                    )


def _group_registrations_by_owner(state: _BuildState) -> None:
    for route in state.routes:
        state.routes_by_owner.setdefault(route.owner, []).append(route)
    for hook in state.hooks:
        state.hooks_by_owner.setdefault(hook.owner, []).append(hook)
    for include in state.includes:
        state.includes_by_owner.setdefault(include.owner, []).append(include)


def _build_world_plans(state: _BuildState) -> tuple[WorldPlan, ...]:
    _group_registrations_by_owner(state)
    world_configs = state.config.worlds or _auto_worlds(state)
    plans: list[WorldPlan] = []
    for world_config in world_configs:
        world_id = WorldId(world_config.profile, world_config.scenario)
        roots: set[NodeId] = set()
        retained: set[NodeId] = set()
        conservative: set[NodeId] = set()
        limitations: list[Limitation] = []
        root_provenance: dict[NodeId, RootProvenance] = {}
        assembly = AssemblyState.COMPLETE
        for root in world_config.roots:
            found: set[NodeId] = set()
            provenance_kind, provenance_detail = _root_provenance(state, world_config, root)
            symbol = state.program.resolve_symbol(root)
            if symbol is not None:
                found.add(symbol.id)
                found.add(state.program.modules[symbol.module].node_id)
                factory_app = state.app_factories.get(symbol.id)
                if factory_app is not None:
                    app_roots, app_limits = _roots_for_app(state, factory_app, world_id)
                    found.update(app_roots)
                    limitations.extend(app_limits)
                    if app_limits:
                        assembly = AssemblyState.PARTIAL
            elif (module := state.program.modules.get(root)) is not None:
                found.add(module.node_id)
            else:
                object_key = _configured_object_key(state, root)
                value_root = _module_value_root(state, root) if object_key is None else None
                if value_root is not None:
                    module_name, name = value_root
                    found.add(state.program.modules[module_name].node_id)
                    if f"{module_name}:{name}" not in state.applications:
                        if assembly is not AssemblyState.INVALID:
                            assembly = AssemblyState.PARTIAL
                        limitations.append(
                            Limitation(
                                code="DT3005",
                                message=f"root names a value whose call is not modeled: {root}",
                                world=world_id,
                            )
                        )
                elif object_key is None:
                    assembly = AssemblyState.INVALID
                    limitations.append(
                        Limitation(
                            code="DT3004",
                            message=(
                                "no Python source files were found below the root"
                                if not state.program.modules
                                else "no execution roots were found: no application, entry "
                                "point, script with a main guard, or public module; configure "
                                "[[tool.deadtrace.worlds]] roots"
                            ),
                            world=world_id,
                        )
                        if root == AUTO_ROOT
                        else Limitation(
                            code="DT3001",
                            message=f"configured root cannot be resolved: {root}",
                            world=world_id,
                        )
                    )
                else:
                    obj = state.objects[object_key]
                    found.add(state.program.modules[obj.module].node_id)
                    if obj.kind is FrameworkObjectKind.FASTAPI_APP:
                        app_roots, app_limits = _roots_for_app(state, object_key, world_id)
                        found.update(app_roots)
                        limitations.extend(app_limits)
                        if app_limits:
                            assembly = AssemblyState.PARTIAL
                    elif obj.kind is FrameworkObjectKind.FASTAPI_ROUTER:
                        router_roots, router_limits = _roots_for_router(
                            state, object_key, world_id, app_key=None
                        )
                        found.update(router_roots)
                        limitations.extend(router_limits)
                        if router_limits:
                            assembly = AssemblyState.PARTIAL
                    else:
                        assembly = AssemblyState.INVALID
                        limitations.append(
                            Limitation(
                                code="DT3002",
                                message=f"container is not an executable application root: {root}",
                                world=world_id,
                            )
                        )
            for node_id in found:
                if node_id not in root_provenance:
                    root_provenance[node_id] = RootProvenance(
                        node_id, provenance_kind, provenance_detail
                    )
            roots.update(found)
        if not state.config.worlds and state.entry_point_issues:
            if assembly is not AssemblyState.INVALID:
                assembly = AssemblyState.PARTIAL
            limitations.extend(
                Limitation(code=issue.code, message=issue.message, world=world_id)
                for issue in state.entry_point_issues
            )
        for keep in state.config.keep:
            if world_config.profile not in keep.profiles:
                continue
            symbol = state.program.resolve_symbol(keep.target)
            if symbol is None:
                if assembly is not AssemblyState.INVALID:
                    assembly = AssemblyState.PARTIAL
                limitations.append(
                    Limitation(
                        code="DT3003",
                        message=f"external keep target cannot be resolved: {keep.target}",
                        world=world_id,
                    )
                )
            else:
                retained.add(symbol.id)
                conservative.add(symbol.id)
        if not roots and assembly is AssemblyState.COMPLETE:
            assembly = AssemblyState.INVALID
            limitations.append(
                Limitation(
                    code="DT3004",
                    message="world has no executable roots",
                    world=world_id,
                )
            )
        plans.append(
            WorldPlan(
                id=world_id,
                roots=tuple(sorted(roots)),
                retained_roots=tuple(sorted(retained)),
                conservative_roots=tuple(sorted(conservative)),
                assembly_state=assembly,
                limitations=tuple(sorted(set(limitations), key=_core_limitation_sort_key)),
                root_provenance=tuple(root_provenance.values()),
                boundaries=(
                    _public_override_boundaries(state, roots)
                    if world_config.scenario == "library" and not state.config.worlds
                    else ()
                ),
            )
        )
    migrations = _migrations_plan(state)
    if migrations is not None:
        plans.append(migrations)
    commands = None if state.config.worlds else _commands_plan(state)
    if commands is not None:
        plans.append(commands)
    return tuple(sorted(plans, key=lambda item: item.id))


def _public_override_boundaries(
    state: _BuildState, roots: set[NodeId]
) -> tuple[UnknownBoundary, ...]:
    """Callers of a library's public methods may hold an instance of a project subclass.

    A user of ``open_process() -> Process`` calls ``terminate`` on whatever it returns, which is
    the override of a private implementation class. The override runs once its class may, so the
    boundary is gated by the class: an implementation nothing constructs stays unreached
    (ADR-0025).
    """

    program = state.program
    subclasses: defaultdict[NodeId, list[PythonSymbol]] = defaultdict(list)
    for symbol in program.symbols.values():
        if symbol.kind is not NodeKind.CLASS:
            continue
        module = program.modules[symbol.module]
        for base in symbol.bases:
            target = program.resolve_symbol(_expanded_name(module, base))
            if target is not None and target.kind is NodeKind.CLASS:
                subclasses[target.id].append(symbol)
    if not subclasses:
        return ()
    boundaries: list[UnknownBoundary] = []
    for node_id in sorted(roots):
        method = program.symbols.get(node_id)
        owner = program.symbols.get(method.owner) if method and method.owner else None
        if method is None or owner is None or not is_function(method):
            continue
        gates: dict[NodeId, NodeId] = {}
        queue = list(subclasses.get(owner.id, ()))
        seen = {owner.id}
        while queue:
            subclass = queue.pop()
            if subclass.id in seen:
                continue
            seen.add(subclass.id)
            override = program.resolve_symbol(
                f"{subclass.module}.{subclass.qualified_name}.{method.name}"
            )
            if override is not None and is_function(override):
                gates[override.id] = subclass.id
            queue.extend(subclasses.get(subclass.id, ()))
        if gates:
            boundaries.append(
                UnknownBoundary(
                    source=method.id,
                    domain="public_override",
                    reason=(
                        f"public method {owner.qualified_name}.{method.name} may be called on an"
                        " instance of a project subclass"
                    ),
                    targets=tuple(sorted(gates)),
                    gates=tuple(sorted(gates.items())),
                )
            )
    return tuple(boundaries)


COMMANDS_WORLD = WorldId("production", "commands")


def _commands_plan(state: _BuildState) -> WorldPlan | None:
    """The world of programs that deployment files start by name (ADR-0023).

    A command's module runs, and the application, worker, or callable it names is a root; a
    class a configuration names is instantiated by the program that reads it, which may call any
    of its methods, so the class and its methods are conservative, retained roots. So are the
    top-level definitions of a module the program reads by name, such as gunicorn hooks or
    locust users, and the methods of its classes.
    """

    roots: set[NodeId] = set()
    conservative: set[NodeId] = set()
    provenance: dict[NodeId, RootProvenance] = {}

    def add(node_id: NodeId, reference: DeploymentReference, into: set[NodeId]) -> None:
        into.add(node_id)
        provenance.setdefault(
            node_id,
            RootProvenance(
                node_id, "deployment_command", f"{reference.source}: {reference.target}"
            ),
        )

    def expose(symbol: PythonSymbol, reference: DeploymentReference) -> None:
        add(symbol.id, reference, conservative)
        conservative.update(
            member.id for member in state.program.index.members(symbol.id) if is_function(member)
        )

    for reference in state.deployment:
        if reference.kind == "script":
            modules = [(module, "") for module in _modules_at_path(state, reference)]
        elif reference.kind == "discovery":
            modules = [
                (module, "")
                for key, module in sorted(state.program.modules.items())
                if key.rpartition(".")[2] == reference.target
            ]
        else:
            module_part, _, attribute = reference.target.partition(":")
            modules = [
                (module, remainder or attribute)
                for module, remainder in _deployment_modules(state, module_part, reference.source)
            ]
        for module, name in modules:
            add(module.node_id, reference, roots)
            if reference.exposed and not name:
                for definition in module.symbols:
                    if definition.owner is None:
                        expose(definition, reference)
            symbol = _deployment_symbol(state, module, name) if name else None
            if symbol is None:
                continue
            if reference.kind == "object":
                expose(symbol, reference)
            else:
                add(symbol.id, reference, roots)
    if not roots:
        return None
    return WorldPlan(
        id=COMMANDS_WORLD,
        roots=tuple(sorted(roots)),
        retained_roots=tuple(sorted(conservative)),
        conservative_roots=tuple(sorted(conservative)),
        assembly_state=AssemblyState.COMPLETE,
        root_provenance=tuple(provenance[key] for key in sorted(provenance)),
    )


def _deployment_symbol(state: _BuildState, module: PythonModule, name: str) -> PythonSymbol | None:
    """The definition ``name`` of ``module`` names, or of the longest prefix that is one."""

    parts = name.split(".")
    for cut in range(len(parts), 0, -1):
        symbol = state.program.resolve_symbol(f"{module.name}:{'.'.join(parts[:cut])}")
        if symbol is not None:
            return symbol
    return None


EXTERNAL_COMMAND_MODULES = frozenset(
    {
        "alembic",
        "black",
        "celery",
        "coverage",
        "django",
        "flake8",
        "gunicorn",
        "hypercorn",
        "isort",
        "locust",
        "mypy",
        "pip",
        "pylint",
        "pytest",
        "ruff",
        "setuptools",
        "twine",
        "uvicorn",
        "wheel",
    }
)
"""Tools that commands run with ``python -m``: their names match no project module by suffix."""


def _deployment_modules(
    state: _BuildState, dotted: str, source: str
) -> list[tuple[PythonModule, str]]:
    """Project modules a dotted name from a command names, with the rest of the name.

    A service runs from its own directory, so ``svc.main`` names the module ``svc.main`` or a
    module ``services.svc.main`` whose prefix ``services`` is a directory and no regular
    package: inside a package, ``logging`` in ``pkg.config.logging`` is no top-level name. A name
    that starts with a standard-library module or a tool, as ``logging.handlers.X`` or
    ``pip``, names only a project module of exactly that name. ``pkg.mod.Worker`` names the
    module ``pkg.mod`` and its ``Worker`` when no module ``pkg.mod.Worker`` exists. Modules
    below the directory of the file naming them are preferred to the others.
    """

    modules = state.program.modules
    directory = source.rpartition("/")[0]
    parts = dotted.split(".")
    external = parts[0] in sys.stdlib_module_names or parts[0] in EXTERNAL_COMMAND_MODULES
    for cut in range(len(parts), 0, -1):
        name = ".".join(parts[:cut])
        remainder = ".".join(parts[cut:])
        found = [
            module
            for key, module in modules.items()
            if key == name
            or (not external and key.endswith(f".{name}") and key[: -len(name) - 1] not in modules)
        ]
        local = [module for module in found if module.path.startswith(f"{directory}/")]
        if directory and local:
            found = local
        if found:
            return [(module, remainder) for module in sorted(found, key=lambda item: item.name)]
    return []


def _modules_at_path(state: _BuildState, reference: DeploymentReference) -> list[PythonModule]:
    """Project modules a script path in a command may be.

    The path is resolved beside the file naming it and from the root; an absolute container path
    such as ``/app/tools/seed.py`` drops leading directories until one of those matches. A path
    of two or more parts also matches a module path that ends with it, as when a service's
    directory is the working directory; a bare file name matches only beside the file or at the
    root.
    """

    by_path = {module.path: module for module in state.program.modules.values()}
    base = reference.source.rpartition("/")[0]
    target = reference.target.replace("\\", "/")
    if not target.startswith("/"):
        joined = posixpath.normpath(posixpath.join(base, target))
        if joined in by_path:
            return [by_path[joined]]
    parts = [part for part in target.split("/") if part not in {"", ".", ".."}]
    for start in range(len(parts)):
        suffix = "/".join(parts[start:])
        exact = sorted({f"{base}/{suffix}" if base else suffix, suffix} & by_path.keys())
        if exact:
            return [by_path[path] for path in exact]
        if len(parts) - start >= 2:
            found = sorted(path for path in by_path if path.endswith(f"/{suffix}"))
            if found:
                return [by_path[path] for path in found]
    return []


MIGRATIONS_WORLD = WorldId("production", "migrations")


def _migrations_plan(state: _BuildState) -> WorldPlan | None:
    """The world of database migrations, which their tool runs apart from any application.

    Alembic runs its environment and revision functions, and Django its migration modules and
    ``RunPython`` callbacks, as ``alembic upgrade`` or ``manage.py migrate``. Rooting them in
    every application world made each application of a monorepo run every service's migrations
    and everything they import (ADR-0022).
    """

    contracts = state.migration_callbacks | state.migration_declarations
    if not contracts and not state.unknown_migration_modules:
        return None
    assembly = AssemblyState.COMPLETE
    conservative: set[NodeId] = set()
    limitations: list[Limitation] = []
    for module_name in sorted(state.unknown_migration_modules):
        module = state.program.modules[module_name]
        conservative.add(module.node_id)
        assembly = AssemblyState.PARTIAL
        limitations.append(
            Limitation(
                code="DT3301",
                message=f"Django RunPython callback cannot be resolved in {module.path}",
                origin=module.node_id,
                world=MIGRATIONS_WORLD,
            )
        )
        state.boundaries.append(
            UnknownBoundary(
                source=module.node_id,
                domain="django_migration_callback",
                reason="unresolved historical migration callback",
                targets=tuple(node.id for node in state.program.graph.nodes),
            )
        )
    # The tool imports each migration module; what it then calls stays a conservative,
    # retained historical contract, as before in every application world.
    modules = {
        state.program.modules[symbol.module].node_id
        if (symbol := state.program.symbols.get(node_id)) is not None
        else node_id
        for node_id in contracts
    }
    conservative.update(contracts)
    return WorldPlan(
        id=MIGRATIONS_WORLD,
        roots=tuple(sorted(modules)),
        retained_roots=tuple(sorted(contracts)),
        conservative_roots=tuple(sorted(conservative)),
        assembly_state=assembly,
        limitations=tuple(sorted(set(limitations), key=_core_limitation_sort_key)),
        root_provenance=tuple(
            RootProvenance(node_id, "framework_discovery", "migration run by its migration tool")
            for node_id in sorted(modules)
        ),
    )


def _auto_worlds(state: _BuildState) -> tuple[WorldConfig, ...]:
    apps = sorted(
        obj.key for obj in state.objects.values() if obj.kind is FrameworkObjectKind.FASTAPI_APP
    )
    entry_worlds = tuple(
        WorldConfig(
            profile="production",
            scenario=entry_point.scenario,
            roots=(entry_point.target, *_plugin_hooks(state, entry_point)),
            frameworks=("python",),
        )
        for entry_point in state.entry_points
    )
    app_worlds = tuple(
        WorldConfig(
            profile="production",
            scenario="web" if len(apps) == 1 else f"web:{app.replace(':', '.')}",
            roots=(app,),
        )
        for app in apps
    )
    worlds = [*app_worlds, *_application_worlds(state), *entry_worlds]
    # A pytest plugin's package is a library its users' tests import, whatever else the project
    # provides (ADR-0019).
    plugin_packages = {
        entry.target.partition(":")[0].split(".")[0]
        for entry in state.entry_points
        if entry.group == "pytest11"
    }
    if not worlds:
        worlds.extend(_library_world(state))
    else:
        if plugin_packages:
            worlds.extend(_library_world(state, plugin_packages))
        worlds.extend(_export_world(state))
    worlds.extend(_script_world(state))
    if not worlds:
        return (WorldConfig("production", "application", (AUTO_ROOT,)),)
    return tuple(worlds)


def _plugin_hooks(state: _BuildState, entry_point: ProjectEntryPoint) -> tuple[str, ...]:
    """The ``pytest_*`` hook functions of a ``pytest11`` plugin module; pytest calls them."""

    if entry_point.group != "pytest11":
        return ()
    module = state.program.modules.get(entry_point.target.partition(":")[0])
    if module is None:
        return ()
    exports = [
        symbol
        for symbol in module.symbols
        if symbol.owner is None
        and is_function(symbol)
        and (symbol.name.startswith("pytest_") or _is_fixture(module, symbol))
    ]
    hooks = tuple(
        dict.fromkeys(
            (
                *(f"{module.name}:{symbol.name}" for symbol in exports),
                *_returned_api(state, module, exports),
            )
        )
    )
    for hook in hooks:
        state.auto_provenance[(entry_point.scenario, hook)] = (
            "project_entry_point",
            f"pyproject.toml {entry_point.group}:{entry_point.name} hook",
        )
    return hooks


def _returned_api(
    state: _BuildState, module: PythonModule, exports: list[PythonSymbol]
) -> list[str]:
    """Public methods of the project classes a plugin fixture's return annotation names.

    A fixture hands its value to the plugin's users, whose tests call its public methods, as the
    library world treats an API class (ADR-0019).
    """

    program = state.program
    roots: list[str] = []
    for symbol in exports:
        if symbol.return_annotation is None:
            continue
        for name in _annotation_names(symbol.return_annotation, module.text):
            first, _, rest = name.partition(".")
            binding = module.imports.get(first)
            full = (
                (f"{binding.target}.{rest}" if rest else binding.target)
                if binding is not None
                else f"{module.name}.{name}"
            )
            target = program.resolve_symbol(full)
            if target is None or target.kind is not NodeKind.CLASS:
                continue
            roots.extend(
                f"{member.module}:{member.qualified_name}"
                for member in program.index.members(target.id)
                if is_function(member) and not member.name.startswith("_")
            )
    return roots


def _is_fixture(module: PythonModule, symbol: PythonSymbol) -> bool:
    """Whether ``pytest.fixture`` decorates a function: a plugin exports it to its users."""

    return any(
        is_fixture_decorator(
            _expanded_name(
                module, expression.func if isinstance(expression, ast.Call) else expression
            )
        )
        for expression in symbol.decorators
    )


def _application_worlds(state: _BuildState) -> tuple[WorldConfig, ...]:
    """One world per application of a framework without a capability."""

    by_framework: defaultdict[str, list[tuple[str, str]]] = defaultdict(list)
    for key, (framework, root) in sorted(state.applications.items()):
        by_framework[framework].append((key, root))
    worlds: list[WorldConfig] = []
    for framework, items in sorted(by_framework.items()):
        for key, root in items:
            scenario = framework if len(items) == 1 else f"{framework}:{key.replace(':', '.')}"
            state.auto_provenance[(scenario, root)] = ("framework_application", key)
            worlds.append(WorldConfig("production", scenario, (root,), ("python",)))
    return tuple(worlds)


def _script_world(state: _BuildState) -> tuple[WorldConfig, ...]:
    """Modules run as programs: ``__main__`` modules and modules with a main guard."""

    scripts = sorted(
        name
        for name, module in state.program.modules.items()
        if not _is_test_file(module)
        and (name.rpartition(".")[2] == "__main__" or has_main_guard(module))
    )
    for name in scripts:
        state.auto_provenance[("scripts", name)] = ("main_module", name)
    return (WorldConfig("production", "scripts", tuple(scripts), ("python",)),) if scripts else ()


def _library_world(state: _BuildState, packages: set[str] | None = None) -> tuple[WorldConfig, ...]:
    """Roots for a project without applications or entry points: its public API.

    Public modules are those whose dotted name has no part starting with an underscore, outside
    test, documentation, example, and benchmark directories. A public module's API is its
    top-level names without a leading underscore, the names a literal ``__all__`` lists, and, for
    a package, the names it imports without a leading underscore, star imports included. Callers
    reach names that ``__all__`` leaves out as attributes, so the list only adds to the API. The
    public methods and nested classes of an API class are API too.
    """

    program = state.program
    roots: dict[str, None] = {}
    for name, module in sorted(program.modules.items()):
        if _is_non_library_module(module) or any(part.startswith("_") for part in name.split(".")):
            continue
        if packages is not None and name.split(".")[0] not in packages:
            continue
        roots[name] = None
        exports = declared_exports(module) or frozenset()
        is_package = module.path.endswith("__init__.py")
        api = [
            symbol
            for symbol in module.symbols
            if symbol.owner is None and (not symbol.name.startswith("_") or symbol.name in exports)
        ]
        for local, binding in module.imports.items():
            if not (is_package and not local.startswith("_")) and local not in exports:
                continue
            # A name imported in both branches of a condition, one of them from a module
            # without source (a compiled extension), is the project's whichever branch ran.
            for item in module.import_alternatives.get(local) or (binding,):
                target = program.resolve_symbol(item.target)
                if target is not None:
                    api.append(target)
        if is_package:
            api.extend(
                symbol
                for base in module.star_imports
                for symbol in program.modules[base].symbols
                if symbol.owner is None and not symbol.name.startswith("_")
            )
        while api:
            symbol = api.pop()
            full_name = f"{symbol.module}:{symbol.qualified_name}"
            if full_name in roots:
                continue
            roots[full_name] = None
            if symbol.kind is NodeKind.CLASS:
                api.extend(
                    member
                    for member in program.index.members(symbol.id)
                    if not member.name.startswith("_")
                )
    for root in roots:
        state.auto_provenance[("library", root)] = ("library_public_api", root)
    return (WorldConfig("production", "library", tuple(roots), ("python",)),) if roots else ()


def _export_world(state: _BuildState) -> tuple[WorldConfig, ...]:
    """The API a top-level package exports explicitly, next to an application (ADR-0026).

    A library with a command line, such as Typer or Click, has applications, so its public API is
    no world of its own. Names the package's ``__init__`` re-exports with ``import y as y`` or lists
    in ``__all__`` are its contract; the rest of the package stays under the usual rules.
    """

    program = state.program
    api: list[PythonSymbol] = []
    for name, module in sorted(program.modules.items()):
        if "." in name or not module.path.endswith("__init__.py") or _is_test_module(module):
            continue
        exports = declared_exports(module) or frozenset()
        explicit = {
            alias.asname
            for statement in module.tree.body
            if isinstance(statement, ast.Import | ast.ImportFrom)
            for alias in statement.names
            if alias.asname is not None and alias.asname == alias.name.rpartition(".")[2]
        }
        for local, binding in module.imports.items():
            if local in exports or local in explicit:
                for item in module.import_alternatives.get(local) or (binding,):
                    target = program.resolve_symbol(item.target)
                    if target is not None:
                        api.append(target)
        api.extend(
            symbol for symbol in module.symbols if symbol.owner is None and symbol.name in exports
        )
    roots: dict[str, None] = {}
    while api:
        symbol = api.pop()
        full_name = f"{symbol.module}:{symbol.qualified_name}"
        if full_name in roots:
            continue
        roots[full_name] = None
        if symbol.kind is NodeKind.CLASS:
            api.extend(
                member
                for member in program.index.members(symbol.id)
                if not member.name.startswith("_")
            )
    for root in roots:
        state.auto_provenance[("exports", root)] = ("package_exports", root)
    return (WorldConfig("production", "exports", tuple(roots), ("python",)),) if roots else ()


def _is_test_module(module: PythonModule) -> bool:
    return is_test_path(module.path)


def _is_test_file(module: PythonModule) -> bool:
    """A module pytest would collect by its file name; a script in a test directory is not one."""

    name = module.path.rpartition("/")[2]
    return name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py"


def _is_non_library_module(module: PythonModule) -> bool:
    directories = module.path.split("/")[:-1]
    return _is_test_module(module) or any(
        directory in _NON_LIBRARY_DIRECTORIES for directory in directories
    )


def _application_framework(
    state: _BuildState, module: PythonModule, constructor: ast.expr
) -> str | None:
    """The framework whose application a call builds, through project subclasses too."""

    name = _expanded_name(module, constructor)
    if name in APPLICATION_CONSTRUCTORS:
        return APPLICATION_CONSTRUCTORS[name]
    symbol = state.program.resolve_symbol(name)
    seen: set[NodeId] = set()
    stack = [symbol] if symbol is not None and symbol.kind is NodeKind.CLASS else []
    while stack:
        class_symbol = stack.pop()
        if class_symbol.id in seen or not isinstance(class_symbol.node, ast.ClassDef):
            continue
        seen.add(class_symbol.id)
        owner = state.program.modules[class_symbol.module]
        for base in class_symbol.node.bases:
            base_name = _expanded_name(owner, base)
            if base_name in APPLICATION_CONSTRUCTORS:
                return APPLICATION_CONSTRUCTORS[base_name]
            base_symbol = state.program.resolve_symbol(base_name)
            if base_symbol is not None and base_symbol.kind is NodeKind.CLASS:
                stack.append(base_symbol)
    return None


def _discover_arq_workers(state: _BuildState) -> None:
    """``arq module.WorkerSettings`` runs a class with ``functions`` or ``cron_jobs``."""

    for module in state.program.modules.values():
        if _is_test_module(module) or not any(
            binding.target == "arq" or binding.target.startswith("arq.")
            for binding in module.imports.values()
        ):
            continue
        for statement in module.tree.body:
            if isinstance(statement, ast.ClassDef) and any(
                isinstance(target, ast.Name) and target.id in ARQ_WORKER_ATTRIBUTES
                for item in statement.body
                for target in (
                    item.targets
                    if isinstance(item, ast.Assign)
                    else [item.target]
                    if isinstance(item, ast.AnnAssign) and item.value is not None
                    else []
                )
            ):
                key = f"{module.name}:{statement.name}"
                state.applications[key] = ("arq", key)


def _discover_application_factories(state: _BuildState) -> None:
    """Top-level functions that build an application, such as a Flask ``create_app``."""

    for module in state.program.modules.values():
        if not any(
            binding.target.partition(".")[0] in _APPLICATION_PACKAGES
            for binding in module.imports.values()
        ):
            continue
        for symbol in module.symbols:
            if symbol.owner is not None or not is_function(symbol):
                continue
            key = f"{module.name}:{symbol.qualified_name}"
            for node in ast.walk(symbol.node):
                if not isinstance(node, ast.Call):
                    continue
                framework = APPLICATION_CONSTRUCTORS.get(_expanded_name(module, node.func))
                if framework is not None:
                    state.applications[key] = (framework, key)
                    break


TYPER_REGISTRARS = frozenset({"command", "callback", "result_callback"})
CLICK_REGISTRARS = frozenset({"command", "group", "result_callback"})
CLICK_ROOTS = frozenset(
    {"click.group", "click.command", "click.decorators.group", "click.decorators.command"}
)


def _discover_cli_commands(state: _BuildState) -> None:
    """Commands that a Typer application or a Click group registers (``cli.commands``).

    ``@app.command()`` and ``@app.callback()`` on a module-level ``typer.Typer()`` register the
    function when the module runs, and running the application may call any of them; the module
    reaches them. ``@click.group()`` makes a function a group, and ``@group.command()`` or
    ``@group.group()`` registers a subcommand that invoking the group may call; the group
    reaches it.
    """

    program = state.program
    typer_apps = {
        key.replace(":", ".", 1)
        for key, (framework, _root) in state.applications.items()
        if framework == "typer"
    }
    groups: dict[str, NodeId] = {}
    for module in program.modules.values():
        for symbol in module.symbols:
            if not is_function(symbol):
                continue
            for expression in symbol.decorators:
                function = expression.func if isinstance(expression, ast.Call) else expression
                if _expanded_name(module, function) in CLICK_ROOTS:
                    groups[f"{module.name}.{symbol.qualified_name}"] = symbol.id
    for module in program.modules.values():
        for symbol in module.symbols:
            if not is_function(symbol):
                continue
            for expression in symbol.decorators:
                if not (
                    isinstance(expression, ast.Call) and isinstance(expression.func, ast.Attribute)
                ):
                    continue
                owner = _expanded_name(module, expression.func.value)
                if owner in typer_apps and expression.func.attr in TYPER_REGISTRARS:
                    state.edges.append(
                        ExecutionEdge(
                            module.node_id,
                            symbol.id,
                            EdgeKind.FRAMEWORK,
                            f"Typer application {owner} registers the command",
                        )
                    )
                elif owner in groups and expression.func.attr in CLICK_REGISTRARS:
                    state.edges.append(
                        ExecutionEdge(
                            groups[owner],
                            symbol.id,
                            EdgeKind.FRAMEWORK,
                            f"Click group {owner} dispatches to the command",
                        )
                    )


def _discover_django_applications(state: _BuildState) -> None:
    """Django settings modules and the modules of installed applications that Django imports.

    A settings module is one that assigns ``INSTALLED_APPS`` at its top level. The applications
    are the strings in that list and in lists assigned to other ``*_APPS`` names of the module.
    When the settings run, Django imports each project application's package, its ``apps``,
    ``models``, and ``admin`` modules, registers the classes its ``models`` modules define, and
    may load any module under its ``management.commands`` and ``templatetags`` packages,
    instantiating a command's ``Command``.
    """

    program = state.program
    for module in program.modules.values():
        installed = _django_installed_apps(module)
        if installed is None:
            continue
        state.applications[module.name] = ("django", module.name)
        packages = sorted(
            {
                package
                for app in installed
                if (package := _django_app_package(state, app)) is not None
            }
        )
        for package in packages:
            prefixes = tuple(f"{package}.{name}." for name in DJANGO_APP_PACKAGES)
            for name, candidate in sorted(program.modules.items()):
                if name.startswith(prefixes[0]) and name.rpartition(".")[2].startswith("_"):
                    continue  # Django lists only commands whose names do not start with "_"
                if name in {package, *(f"{package}.{item}" for item in DJANGO_APP_MODULES)} or (
                    name.startswith(prefixes)
                ):
                    state.edges.append(
                        ExecutionEdge(
                            module.node_id,
                            candidate.node_id,
                            EdgeKind.IMPORT,
                            f"Django imports installed application module {name}",
                        )
                    )
                if name == f"{package}.models" or name.startswith(f"{package}.models."):
                    state.edges.extend(
                        ExecutionEdge(
                            candidate.node_id,
                            symbol.id,
                            EdgeKind.CONSTRUCT,
                            "Django registers the model classes of installed applications",
                        )
                        for symbol in candidate.symbols
                        if symbol.owner is None
                        and symbol.kind is NodeKind.CLASS
                        and any(_dotted_name(base) not in {None, "object"} for base in symbol.bases)
                    )
                if name.startswith(prefixes[0]):
                    command = program.resolve_symbol(f"{name}:Command")
                    if command is not None and command.kind is NodeKind.CLASS:
                        state.edges.append(
                            ExecutionEdge(
                                candidate.node_id,
                                command.id,
                                EdgeKind.CONSTRUCT,
                                "Django instantiates the management command",
                            )
                        )
                if name == f"{package}.apps":
                    state.edges.extend(
                        ExecutionEdge(
                            candidate.node_id,
                            symbol.id,
                            EdgeKind.CONSTRUCT,
                            "Django instantiates the application configuration",
                        )
                        for symbol in candidate.symbols
                        if symbol.owner is None
                        and symbol.kind is NodeKind.CLASS
                        and any(
                            _expanded_name(candidate, _unstarred(base)).endswith("AppConfig")
                            for base in symbol.bases
                        )
                    )
        for server_module in _django_server_modules(state):
            state.edges.append(
                ExecutionEdge(
                    module.node_id,
                    server_module.node_id,
                    EdgeKind.IMPORT,
                    f"an application server loads {server_module.name}",
                )
            )


def _django_server_modules(state: _BuildState) -> list[PythonModule]:
    """Modules that build the ASGI or WSGI application an application server loads by name.

    ``asgi.py`` and ``wsgi.py`` call ``get_asgi_application`` or ``get_wsgi_application`` at
    their top level; a server such as Gunicorn, Uvicorn, or Daphne imports them, whether or not
    ``WSGI_APPLICATION`` or ``ASGI_APPLICATION`` names them in a branch that runs (ADR-0017).
    """

    found: list[PythonModule] = []
    for module in state.program.modules.values():
        if "_application" not in module.unit.source:
            continue
        for node in flow_nodes(module.tree.body):
            if isinstance(node, ast.Call) and _expanded_name(module, node.func).endswith(
                ("get_asgi_application", "get_wsgi_application")
            ):
                found.append(module)
                break
    return sorted(found, key=lambda item: item.name)


def _django_installed_apps(module: PythonModule) -> list[str] | None:
    """Strings of ``INSTALLED_APPS`` and other ``*_APPS`` lists, or ``None`` without the former."""

    found = False
    apps: list[str] = []
    for statement in module.tree.body:
        if isinstance(statement, ast.Assign):
            targets = statement.targets
        elif isinstance(statement, ast.AugAssign | ast.AnnAssign) and statement.value is not None:
            targets = [statement.target]
        else:
            continue
        names = {target.id for target in targets if isinstance(target, ast.Name)}
        if not any(name == "INSTALLED_APPS" or name.endswith("_APPS") for name in names):
            continue
        found = found or "INSTALLED_APPS" in names
        assert statement.value is not None
        apps.extend(
            node.value
            for node in ast.walk(statement.value)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        )
    return apps if found else None


def _django_app_package(state: _BuildState, app: str) -> str | None:
    """The project package an ``INSTALLED_APPS`` entry names, directly or by its ``AppConfig``."""

    program = state.program
    if app in program.modules:
        return app
    config = program.resolve_symbol(app)
    if config is None or config.kind is not NodeKind.CLASS:
        return None
    assert isinstance(config.node, ast.ClassDef)
    for statement in config.node.body:
        if (
            isinstance(statement, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "name" for target in statement.targets
            )
            and isinstance(statement.value, ast.Constant)
            and isinstance(statement.value.value, str)
            and statement.value.value in program.modules
        ):
            return statement.value.value
    package = config.module.rpartition(".")[0]
    return package if package in program.modules else config.module


def _discover_task_autodiscovery(state: _BuildState) -> None:
    """``app.autodiscover_tasks()`` on a Celery application imports modules named ``tasks``.

    The packages it searches come from its arguments or from Django's installed applications, so
    every project module with that name, or the one given as ``related_name``, may be imported.
    """

    for key, (framework, _root) in sorted(state.applications.items()):
        module_name, _, name = key.partition(":")
        if framework != "celery" or name not in state.application_names.get(module_name, ()):
            continue
        module = state.program.modules[module_name]
        for call, _line in _top_level_calls(module):
            func = call.func
            if not (
                isinstance(func, ast.Attribute)
                and func.attr == "autodiscover_tasks"
                and isinstance(func.value, ast.Name)
                and func.value.id == name
            ):
                continue
            related = _keyword_expression(call, "related_name")
            leaf = (
                related.value
                if isinstance(related, ast.Constant) and isinstance(related.value, str)
                else "tasks"
            )
            targets = tuple(
                sorted(
                    candidate.node_id
                    for candidate_name, candidate in state.program.modules.items()
                    if candidate_name.rpartition(".")[2] == leaf
                )
            )
            if targets:
                state.boundaries.append(
                    UnknownBoundary(
                        source=module.node_id,
                        domain="dynamic_import",
                        reason=f"Celery application {key} autodiscovers modules named {leaf}",
                        targets=targets,
                    )
                )


def _root_provenance(state: _BuildState, world: WorldConfig, root: str) -> tuple[str, str]:
    if state.config.worlds:
        return "configured", root
    automatic = state.auto_provenance.get((world.scenario, root))
    if automatic is not None:
        return automatic
    for entry_point in state.entry_points:
        if entry_point.scenario == world.scenario and entry_point.target == root:
            return (
                "project_entry_point",
                f"pyproject.toml {entry_point.group}:{entry_point.name}",
            )
    return "framework_discovery", root


def _roots_for_app(
    state: _BuildState, app_key: str, world: WorldId
) -> tuple[set[NodeId], list[Limitation]]:
    roots, limitations = _roots_for_router(state, app_key, world, app_key=app_key)
    app = state.objects[app_key]
    roots.add(state.program.modules[app.module].node_id)
    roots.update(state.factory_entry_callers.get(app_key, ()))
    container_key = state.app_containers.get(app_key)
    if container_key is not None:
        container = state.objects[container_key]
        conditional = state.conditional_providers.intersection(container.provider_classes)
        if conditional:
            limitations.append(
                Limitation(
                    code="DT3106",
                    message=(
                        "Dishka conditional activation or registry observation is guarded; "
                        "binding selection is not resolved"
                    ),
                    origin=sorted(conditional)[0],
                    world=world,
                )
            )
            state.boundaries.append(
                UnknownBoundary(
                    source=state.program.modules[app.module].node_id,
                    domain="dishka_conditional_activation",
                    reason="conditional provider can observe or change registry selection",
                    targets=tuple(node.id for node in state.program.graph.nodes),
                )
            )
        unsupported = {
            feature
            for provider in container.provider_classes
            for feature in state.unsupported_provider_features.get(provider, set())
        }
        if unsupported:
            limitations.append(
                Limitation(
                    code="DT3107",
                    message=(
                        "Dishka provider features are not modeled: "
                        + ", ".join(sorted(unsupported))
                    ),
                    origin=next(
                        provider
                        for provider in container.provider_classes
                        if state.unsupported_provider_features.get(provider)
                    ),
                    world=world,
                )
            )
            state.boundaries.append(
                UnknownBoundary(
                    source=state.program.modules[app.module].node_id,
                    domain="dishka_unsupported_provider_feature",
                    reason="provider component/decorator semantics can change binding selection",
                    targets=tuple(node.id for node in state.program.graph.nodes),
                )
            )
    return roots, limitations


def _roots_for_router(
    state: _BuildState,
    object_key: str,
    world: WorldId,
    *,
    app_key: str | None,
    inherited_dependencies: tuple[NodeId, ...] = (),
    seen: frozenset[str] = frozenset(),
) -> tuple[set[NodeId], list[Limitation]]:
    if object_key in seen:
        return set(), []
    seen = seen | {object_key}
    obj = state.objects[object_key]
    common_dependencies = tuple(sorted(set((*inherited_dependencies, *obj.dependencies))))
    roots: set[NodeId] = set(common_dependencies)
    limitations: list[Limitation] = []
    if obj.lifespan is not None:
        roots.add(obj.lifespan)
    for hook in state.hooks_by_owner.get(object_key, ()):
        roots.add(hook.callback)
    for route in state.routes_by_owner.get(object_key, ()):
        roots.add(route.endpoint)
        for dependency in (*common_dependencies, *route.dependencies):
            state.edges.append(
                ExecutionEdge(
                    route.endpoint,
                    dependency,
                    EdgeKind.DEPENDENCY,
                    f"FastAPI dependency for {route.path}:{route.line}",
                )
            )
        route_limits = _connect_dishka_route(state, route, obj, app_key, world)
        limitations.extend(route_limits)
        _connect_pydantic_route(state, route)
    for include in state.includes_by_owner.get(object_key, ()):
        child_roots, child_limits = _roots_for_router(
            state,
            include.router,
            world,
            app_key=app_key,
            inherited_dependencies=tuple(
                sorted(set((*common_dependencies, *include.dependencies)))
            ),
            seen=seen,
        )
        roots.update(child_roots)
        limitations.extend(child_limits)
    return roots, limitations


def _connect_dishka_route(
    state: _BuildState,
    route: RouteRegistration,
    owner: FrameworkObject,
    app_key: str | None,
    world: WorldId,
) -> list[Limitation]:
    if not route.dishka_demands:
        return []
    limitations: list[Limitation] = []
    injected = route.explicitly_injected or owner.dishka_route
    if not injected:
        limitations.append(
            Limitation(
                code="DT3101",
                message="FromDishka demand has no active @inject or DishkaRoute integration",
                origin=route.endpoint,
                world=world,
            )
        )
        _guard_dishka_demands(state, route)
        return limitations
    container_key = state.app_containers.get(app_key or "")
    if container_key is None:
        limitations.append(
            Limitation(
                code="DT3102",
                message="FastAPI application has no statically resolved setup_dishka container",
                origin=route.endpoint,
                world=world,
            )
        )
        _guard_dishka_demands(state, route)
        return limitations
    container = state.objects[container_key]
    available = _container_bindings(state, container_key)
    for demand in route.dishka_demands:
        candidates = available.by_provides.get(demand, [])
        context_candidates = available.context_by_provides.get(demand, [])
        if any(
            state.unsupported_provider_features.get(binding.provider_class)
            for binding in candidates
        ):
            _guard_type(
                state,
                route.endpoint,
                demand,
                f"unsupported Dishka provider semantics for {demand}",
            )
            continue
        if any(binding.provider_class in state.conditional_providers for binding in candidates):
            _guard_type(
                state,
                route.endpoint,
                demand,
                f"conditional Dishka binding selection for {demand}",
            )
            continue
        if len(candidates) == 1 and not context_candidates:
            state.edges.append(
                ExecutionEdge(
                    route.endpoint,
                    candidates[0].factory,
                    EdgeKind.DEPENDENCY,
                    f"Dishka resolves endpoint demand {demand}",
                )
            )
            limitations.extend(
                _validate_binding_dependencies(
                    state,
                    candidates[0],
                    available,
                    container,
                    route.endpoint,
                    world,
                    seen=frozenset(),
                )
            )
        elif not candidates and len(context_candidates) == 1:
            context_binding = context_candidates[0]
            if _context_is_available(container, context_binding):
                target = state.program.resolve_symbol(context_binding.provides)
                if target is not None:
                    state.requirements.append(
                        Requirement(
                            source=route.endpoint,
                            target=target.id,
                            kind=EdgeKind.DEPENDENCY,
                            detail=f"Dishka context provides {context_binding.provides}",
                        )
                    )
            else:
                limitations.append(
                    Limitation(
                        code="DT3105",
                        message=f"context value is not supplied for {demand}",
                        origin=route.endpoint,
                        world=world,
                    )
                )
                _guard_type(state, route.endpoint, demand, f"missing context value {demand}")
        else:
            total = len(candidates) + len(context_candidates)
            reason = "no binding" if total == 0 else "multiple bindings"
            limitations.append(
                Limitation(
                    code="DT3103",
                    message=f"{reason} for Dishka demand {demand}",
                    origin=route.endpoint,
                    world=world,
                )
            )
            _guard_type(state, route.endpoint, demand, f"unresolved Dishka demand {demand}")
    return limitations


def _container_bindings(state: _BuildState, container_key: str) -> _ContainerBindings:
    """Bindings of one container's providers, in discovery order; discovery has finished."""

    cached = state.container_bindings.get(container_key)
    if cached is not None:
        return cached
    providers = set(state.objects[container_key].provider_classes)
    by_provides: dict[str, list[ProviderBinding]] = {}
    for binding in state.bindings:
        if binding.provider_class in providers:
            by_provides.setdefault(binding.provides, []).append(binding)
    context_by_provides: dict[str, list[ContextBinding]] = {}
    for context_binding in state.context_bindings:
        if context_binding.provider_class in providers:
            context_by_provides.setdefault(context_binding.provides, []).append(context_binding)
    cached = state.container_bindings[container_key] = _ContainerBindings(
        by_provides, context_by_provides
    )
    return cached


def _validate_binding_dependencies(
    state: _BuildState,
    binding: ProviderBinding,
    available: _ContainerBindings,
    container: FrameworkObject,
    origin: NodeId,
    world: WorldId,
    *,
    seen: frozenset[NodeId],
) -> list[Limitation]:
    if binding.factory in seen:
        return []
    seen = seen | {binding.factory}
    limitations: list[Limitation] = []
    for dependency in binding.dependencies:
        candidates = available.by_provides.get(dependency, [])
        context_candidates = available.context_by_provides.get(dependency, [])
        if not candidates and len(context_candidates) == 1:
            if _context_is_available(container, context_candidates[0]):
                continue
            reason = "context value not supplied"
        elif len(candidates) == 1 and not context_candidates:
            limitations.extend(
                _validate_binding_dependencies(
                    state,
                    candidates[0],
                    available,
                    container,
                    origin,
                    world,
                    seen=seen,
                )
            )
            continue
        else:
            reason = (
                "no binding" if not candidates and not context_candidates else "multiple bindings"
            )
        if reason:
            limitations.append(
                Limitation(
                    code="DT3104",
                    message=f"{reason} for provider dependency {dependency}",
                    origin=origin,
                    world=world,
                )
            )
            _guard_type(
                state,
                origin,
                dependency,
                f"unresolved provider dependency {dependency}",
            )
            continue
    return limitations


def _guard_dishka_demands(state: _BuildState, route: RouteRegistration) -> None:
    for demand in route.dishka_demands:
        _guard_type(state, route.endpoint, demand, "Dishka integration is incomplete")


def _guard_type(state: _BuildState, source: NodeId, type_name: str, reason: str) -> None:
    index = state.program.index
    targets = tuple(
        sorted(
            symbol.id
            for symbols in (index.named(type_name), index.under(f"{type_name}."))
            for symbol in symbols
        )
    )
    state.boundaries.append(
        UnknownBoundary(
            source=source,
            domain="dishka_binding_selection",
            reason=reason,
            targets=targets,
        )
    )


def _pydantic_schema_types(
    program: PythonProgram, module: PythonModule, symbol: PythonSymbol
) -> tuple[str, ...]:
    candidates: set[str] = set()
    annotations = [
        parameter.annotation for parameter in symbol.parameters if parameter.annotation is not None
    ]
    if symbol.return_annotation is not None:
        annotations.append(symbol.return_annotation)
    for annotation in annotations:
        for name in _annotation_names(annotation, module.text):
            expanded = _expand_dotted(module, name)
            target = program.resolve_symbol(expanded)
            if target is not None and _is_pydantic_model(program, target):
                candidates.add(f"{target.module}.{target.qualified_name}")
    return tuple(sorted(candidates))


def _is_pydantic_model(program: PythonProgram, symbol: PythonSymbol) -> bool:
    if not isinstance(symbol.node, ast.ClassDef):
        return False
    module = program.modules[symbol.module]
    for base in symbol.bases:
        name = _expanded_name(module, base)
        if name in {"pydantic.BaseModel", "pydantic.main.BaseModel"}:
            return True
        parent = program.resolve_symbol(name)
        if parent is not None and parent.id != symbol.id and _is_pydantic_model(program, parent):
            return True
    return False


_PYDANTIC_HOOK_DECORATORS = frozenset(
    {
        "pydantic.field_validator",
        "pydantic.functional_validators.field_validator",
        "pydantic.model_validator",
        "pydantic.functional_validators.model_validator",
        "pydantic.field_serializer",
        "pydantic.model_serializer",
        "pydantic.computed_field",
    }
)


def _pydantic_hook_methods(program: PythonProgram, model: PythonSymbol) -> tuple[PythonSymbol, ...]:
    module = program.modules[model.module]
    return tuple(
        method
        for method in program.index.members(model.id)
        if method.name == "model_post_init"
        or method.name.startswith("__get_pydantic")
        or any(
            _expanded_name(module, decorator.func if isinstance(decorator, ast.Call) else decorator)
            in _PYDANTIC_HOOK_DECORATORS
            for decorator in method.decorators
        )
    )


def _connect_pydantic_models(state: _BuildState) -> None:
    """Pydantic runs a model's hooks whenever it validates or serializes an instance."""

    for symbol in state.program.symbols.values():
        if symbol.kind is not NodeKind.CLASS or not _is_pydantic_model(state.program, symbol):
            continue
        for method in _pydantic_hook_methods(state.program, symbol):
            state.pydantic_hooks.add(method.id)
            state.edges.append(
                ExecutionEdge(
                    symbol.id,
                    method.id,
                    EdgeKind.FRAMEWORK,
                    f"Pydantic hook of {symbol.module}.{symbol.qualified_name}",
                )
            )


def _connect_pydantic_route(state: _BuildState, route: RouteRegistration) -> None:
    known_decorators = _PYDANTIC_HOOK_DECORATORS
    for type_name in route.schema_types:
        model = state.program.resolve_symbol(type_name)
        if model is None:
            continue
        state.edges.append(
            ExecutionEdge(
                route.endpoint,
                model.id,
                EdgeKind.FRAMEWORK,
                f"FastAPI/Pydantic schema uses {type_name}",
            )
        )
        module = state.program.modules[model.module]
        for method in state.program.index.members(model.id):
            is_known_hook = any(
                _expanded_name(
                    module,
                    decorator.func if isinstance(decorator, ast.Call) else decorator,
                )
                in known_decorators
                for decorator in method.decorators
            )
            if (
                is_known_hook
                or method.name == "model_post_init"
                or method.name.startswith("__get_pydantic")
            ):
                state.edges.append(
                    ExecutionEdge(
                        route.endpoint,
                        method.id,
                        EdgeKind.FRAMEWORK,
                        f"Pydantic hook for {type_name}",
                    )
                )


def _background_callbacks(
    program: PythonProgram, module: PythonModule, symbol: PythonSymbol
) -> tuple[NodeId, ...]:
    if isinstance(symbol.node, ast.ClassDef):
        return ()
    callbacks: set[NodeId] = set()
    for node in flow_nodes(symbol.node.body):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_task"
        ):
            continue
        arguments = call_arguments(node)
        if not arguments:
            continue
        callback = program.resolve_symbol(_expanded_name(module, arguments[0].value))
        if callback is not None:
            callbacks.add(callback.id)
    return tuple(sorted(callbacks))


def _context_types_from_call(
    program: PythonProgram, module: PythonModule, call: ast.Call
) -> tuple[str, ...]:
    context = _keyword_expression(call, "context")
    if not isinstance(context, ast.Dict):
        return ()
    types: set[str] = set()
    for key in context.keys:
        if key is None:
            continue
        name = _project_or_external_expression_name(program, module, key)
        if name is not None:
            types.add(name)
    return tuple(sorted(types))


def _context_is_available(container: FrameworkObject, binding: ContextBinding) -> bool:
    if binding.provides in container.context_types:
        return True
    return container.has_fastapi_provider and binding.provides in {
        "fastapi.Request",
        "fastapi.WebSocket",
        "starlette.requests.Request",
        "starlette.websockets.WebSocket",
    }


def _is_provider_class(program: PythonProgram, symbol: PythonSymbol) -> bool:
    if not isinstance(symbol.node, ast.ClassDef):
        return False
    module = program.modules[symbol.module]
    for base in symbol.bases:
        name = _expanded_name(module, base)
        if name == "dishka.Provider":
            return True
        parent = program.resolve_symbol(name)
        if parent is not None and parent.id != symbol.id and _is_provider_class(program, parent):
            return True
    return False


def _provider_class_from_expression(
    state: _BuildState, module: PythonModule, expression: ast.expr
) -> PythonSymbol | None:
    if isinstance(expression, ast.Name):
        instance = state.provider_instances.get(f"{module.name}:{expression.id}")
        return state.program.symbols.get(instance) if instance is not None else None
    if not isinstance(expression, ast.Call):
        return None
    symbol = state.program.resolve_symbol(_expanded_name(module, expression.func))
    if symbol is not None and _is_provider_class(state.program, symbol):
        return symbol
    return None


def _constructor_dependencies(
    program: PythonProgram, class_symbol: PythonSymbol
) -> tuple[str, ...]:
    constructor = _constructor_symbol(program, class_symbol)
    if constructor is None:
        return ()
    return tuple(
        dependency
        for parameter in constructor.parameters
        if parameter.name not in {"self", "cls"} and parameter.annotation is not None
        for dependency in [
            _annotation_project_or_external_name(
                program.modules[constructor.module], parameter.annotation
            )
        ]
        if dependency is not None
    )


def _constructor_symbol(program: PythonProgram, class_symbol: PythonSymbol) -> PythonSymbol | None:
    return next(
        (symbol for symbol in program.index.members(class_symbol.id) if symbol.name == "__init__"),
        None,
    )


def _find_decorator(module: PythonModule, symbol: PythonSymbol, names: set[str]) -> ast.expr | None:
    for expression in symbol.decorators:
        function = expression.func if isinstance(expression, ast.Call) else expression
        if _expanded_name(module, function) in names:
            return expression
    return None


def _provider_class_has_condition(module: PythonModule, node: ast.ClassDef) -> bool:
    return _class_assigns_name(module, node, "when")


def _provider_class_has_component(module: PythonModule, node: ast.ClassDef) -> bool:
    return _class_assigns_name(module, node, "component")


def _class_assigns_name(module: PythonModule, node: ast.ClassDef, name: str) -> bool:
    return any(
        isinstance(small, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == name for target in small.targets)
        for small in simple_block_statements(module, node)
    )


def _provider_member_has_condition(module: PythonModule, symbol: PythonSymbol) -> bool:
    for expression in symbol.decorators:
        function = expression.func if isinstance(expression, ast.Call) else expression
        expanded = _expanded_name(module, function)
        if expanded == "dishka.activate":
            return True
        if (
            expanded == "dishka.provide"
            and isinstance(expression, ast.Call)
            and _keyword_expression(expression, "when") is not None
        ):
            return True
    return False


def _decorator_keyword_type(
    program: PythonProgram,
    module: PythonModule,
    decorator: ast.expr,
    keyword: str,
) -> str | None:
    if not isinstance(decorator, ast.Call):
        return None
    expression = _keyword_expression(decorator, keyword)
    if expression is None:
        return None
    return _project_or_external_expression_name(program, module, expression)


def _decorator_keyword_name(module: PythonModule, decorator: ast.expr, keyword: str) -> str | None:
    if not isinstance(decorator, ast.Call):
        return None
    expression = _keyword_expression(decorator, keyword)
    return _expanded_name(module, expression) if expression is not None else None


def _annotation_project_or_external_name(
    module: PythonModule, annotation: ast.expr | None
) -> str | None:
    if annotation is None:
        return None
    names = _annotation_names(annotation, module.text)
    return _expand_dotted(module, names[0]) if names else None


def _project_or_external_expression_name(
    program: PythonProgram, module: PythonModule, expression: ast.expr
) -> str | None:
    name = _expanded_name(module, expression)
    symbol = program.resolve_symbol(name)
    return f"{symbol.module}.{symbol.qualified_name}" if symbol is not None else name


def _parameter_dependencies(
    program: PythonProgram, module: PythonModule, symbol: PythonSymbol
) -> tuple[NodeId, ...]:
    dependencies: set[NodeId] = set()
    for parameter in symbol.parameters:
        expressions: list[ast.expr] = []
        if isinstance(parameter.default, ast.Call):
            expressions.append(parameter.default)
        if isinstance(parameter.annotation, ast.Subscript):
            expressions.extend(
                item
                for item in subscript_elements(parameter.annotation, module.text)
                if isinstance(item, ast.Call)
            )
        for expression in expressions:
            if not isinstance(expression, ast.Call) or not _expanded_name(
                module, expression.func
            ).endswith("Depends"):
                continue
            dependency_expression = _call_argument(expression, "dependency", 0)
            if dependency_expression is None:
                continue
            target = program.resolve_symbol(_expanded_name(module, dependency_expression))
            if target is not None:
                dependencies.add(target.id)
    return tuple(sorted(dependencies))


def _dishka_demands(module: PythonModule, symbol: PythonSymbol) -> tuple[str, ...]:
    demands: set[str] = set()
    for parameter in symbol.parameters:
        annotation = parameter.annotation
        if not isinstance(annotation, ast.Subscript):
            continue
        if _expanded_name(module, annotation.value).endswith("FromDishka"):
            for element in subscript_items(annotation, module.text)[:1]:
                if not isinstance(element, ast.Slice):
                    demand = _project_or_external_annotation_element(module, element)
                    if demand is not None:
                        demands.add(demand)
    return tuple(sorted(demands))


def _project_or_external_annotation_element(
    module: PythonModule, expression: ast.expr
) -> str | None:
    names = _annotation_names(expression, module.text)
    return _expand_dotted(module, names[0]) if names else None


def _dependencies_from_call(
    program: PythonProgram, module: PythonModule, call: ast.Call
) -> tuple[NodeId, ...]:
    expression = _keyword_expression(call, "dependencies")
    if not isinstance(expression, (ast.List, ast.Tuple)):
        return ()
    dependencies: set[NodeId] = set()
    for element in expression.elts:
        depends_call = _unstarred(element)
        if not isinstance(depends_call, ast.Call):
            continue
        if not _expanded_name(module, depends_call.func).endswith("Depends"):
            continue
        target_expression = _call_argument(depends_call, "dependency", 0)
        if target_expression is None:
            continue
        target = program.resolve_symbol(_expanded_name(module, target_expression))
        if target is not None:
            dependencies.add(target.id)
    return tuple(sorted(dependencies))


def _top_level_assignments(
    module: PythonModule,
) -> tuple[tuple[str, ast.expr, int], ...]:
    lines = module.statement_lines
    result: list[tuple[str, ast.expr, int]] = []
    for small in module.tree.body:
        if (
            isinstance(small, ast.Assign)
            and len(small.targets) == 1
            and isinstance(small.targets[0], ast.Name)
        ):
            result.append((small.targets[0].id, small.value, lines[small]))
        elif (
            isinstance(small, ast.AnnAssign)
            and isinstance(small.target, ast.Name)
            and small.value is not None
        ):
            result.append((small.target.id, small.value, lines[small]))
    return tuple(result)


def _fastapi_factory_app(
    state: _BuildState,
    factory: PythonSymbol,
    *,
    wrapped: bool = False,
) -> tuple[str, ast.Call] | None:
    """Recognize one local FastAPI construction that is returned unchanged.

    With ``wrapped``, a factory that constructs exactly one FastAPI application and returns
    something else, such as an ASGI wrapper around it, counts as well.
    """

    assert not isinstance(factory.node, ast.ClassDef)
    constructors: dict[str, ast.Call] = {}
    returned: set[str] = set()
    factory_module = state.program.modules[factory.module]
    for small in simple_block_statements(factory_module, factory.node):
        if (
            isinstance(small, ast.Assign)
            and len(small.targets) == 1
            and isinstance(small.targets[0], ast.Name)
            and isinstance(small.value, ast.Call)
            and _expanded_name(factory_module, small.value.func)
            in {"fastapi.FastAPI", "fastapi.applications.FastAPI"}
        ):
            constructors[small.targets[0].id] = small.value
        elif isinstance(small, ast.Return) and isinstance(small.value, ast.Name):
            returned.add(small.value.id)
    matches = sorted(set(constructors).intersection(returned))
    if not matches and len(constructors) == 1 and wrapped:
        matches = sorted(constructors)  # the application is returned inside a wrapper
    if len(matches) != 1:
        return None
    name = matches[0]
    return name, constructors[name]


def _top_level_calls(module: PythonModule) -> tuple[tuple[ast.Call, int], ...]:
    lines = module.statement_lines
    return tuple(
        (small.value, lines[small])
        for small in module.tree.body
        if isinstance(small, ast.Expr) and isinstance(small.value, ast.Call)
    )


def _expanded_name(module: PythonModule, expression: ast.AST | None) -> str:
    dotted = _dotted_name(expression)
    return _expand_dotted(module, dotted) if dotted is not None else ""


def _expand_dotted(module: PythonModule, dotted: str) -> str:
    first, *rest = dotted.split(".")
    binding = module.imports.get(first)
    if binding is not None:
        return ".".join((binding.target, *rest)) if rest else binding.target
    return f"{module.name}.{dotted}"


def _index_object_keys(state: _BuildState) -> None:
    for key in state.objects:
        object_module, _, object_name = key.partition(":")
        state.object_keys.setdefault(f"{object_module}.{object_name}", key)


def _object_key(state: _BuildState, module: PythonModule, expression: ast.expr) -> str | None:
    return _object_key_for_name(state, _expanded_name(module, expression), 3)


def _object_key_for_name(state: _BuildState, dotted: str, depth: int) -> str | None:
    """The framework object a dotted name reaches, following re-exports of packages.

    ``from app.container import container`` names the object that ``app/container/__init__.py``
    imports from its submodule, not the submodule of the same name: the package binding
    replaces the submodule attribute when the package runs (ADR-0017).
    """

    key = state.object_keys.get(dotted)
    if key is not None or depth == 0:
        return key
    parts = dotted.split(".")
    for cut in range(len(parts) - 1, 0, -1):
        module = state.program.modules.get(".".join(parts[:cut]))
        if module is None:
            continue
        binding = module.imports.get(parts[cut])
        if binding is None:
            return None
        return _object_key_for_name(state, ".".join((binding.target, *parts[cut + 1 :])), depth - 1)
    return None


def _first_argument_object_key(
    state: _BuildState, module: PythonModule, call: ast.Call
) -> str | None:
    arguments = call_arguments(call)
    return _object_key(state, module, arguments[0].value) if arguments else None


def _configured_object_key(state: _BuildState, target: str) -> str | None:
    normalized = target.replace(".", ":", 1) if ":" not in target else target
    if normalized in state.objects:
        return normalized
    dotted = target.replace(":", ".", 1)
    for key in state.objects:
        module, _, name = key.partition(":")
        if f"{module}.{name}" == dotted:
            return key
    return None


def _module_value_root(state: _BuildState, target: str, depth: int = 3) -> tuple[str, str] | None:
    """The module and name of a top-level value that a root such as ``pkg.cli:app`` names.

    An entry point may name an object instead of a function or class: a Typer or Click
    application, say. Running the module binds it; a name the module imports from another
    project module is followed there, as ``pkg:app`` re-exporting ``pkg.cli:app``.
    """

    module_name, _, name = target.partition(":") if ":" in target else target.rpartition(".")
    module = state.program.modules.get(module_name)
    if module is None or not name or "." in name:
        return None
    for statement in module.tree.body:
        targets: list[ast.expr] = []
        if isinstance(statement, ast.Assign):
            targets = list(statement.targets)
        elif isinstance(statement, ast.AnnAssign) and statement.value is not None:
            targets = [statement.target]
        if any(isinstance(item, ast.Name) and item.id == name for item in targets):
            return module_name, name
    binding = module.imports.get(name)
    if binding is None or depth == 0:
        return None
    return _module_value_root(state, binding.target, depth - 1)


def _keyword_expression(call: ast.Call, name: str) -> ast.expr | None:
    return keyword_argument(call, name)


def _call_argument(call: ast.Call, keyword: str, position: int) -> ast.expr | None:
    keyword_value = _keyword_expression(call, keyword)
    if keyword_value is not None:
        return keyword_value
    positional = positional_arguments(call)
    return positional[position] if position < len(positional) else None


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


def _route_sort_key(route: RouteRegistration) -> tuple[str, str, str, int]:
    return (route.owner, str(route.endpoint), route.path, route.line)


def _hook_sort_key(hook: FrameworkHook) -> tuple[str, str, str, int]:
    return (hook.owner, str(hook.callback), hook.path, hook.line)


def _include_sort_key(include: RouterInclude) -> tuple[str, str, str, int]:
    return (include.owner, include.router, include.path, include.line)


def _binding_sort_key(binding: ProviderBinding) -> tuple[str, str, str, int]:
    return (binding.provides, str(binding.factory), binding.path, binding.line)


def _context_binding_sort_key(binding: ContextBinding) -> tuple[str, str, str, int]:
    return (binding.provides, str(binding.provider_class), binding.path, binding.line)


def _core_limitation_sort_key(limitation: Limitation) -> tuple[str, ...]:
    return (
        limitation.world.key if limitation.world else "",
        limitation.code,
        str(limitation.origin or ""),
        limitation.message,
    )
