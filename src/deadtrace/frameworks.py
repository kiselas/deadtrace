"""Built-in FastAPI and Dishka semantic capabilities.

The scanner recognizes documented source patterns without importing target
frameworks. Unsupported assembly weakens the affected world instead of being
treated as absence of execution.
"""

from __future__ import annotations

import ast
from collections import defaultdict
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
    is_function,
    keyword_argument,
    positional_arguments,
    simple_block_statements,
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
    "flask.Flask": "flask",
    "litestar.Litestar": "litestar",
    "quart.Quart": "quart",
    "sanic.Sanic": "sanic",
    "starlette.applications.Starlette": "starlette",
    "typer.Typer": "typer",
}
"""Application constructors of frameworks without a capability. The module or factory that
builds one is an execution root; handlers registered on the application by decorators are
protected by the decorator rule of ADR-0008."""

_APPLICATION_PACKAGES = frozenset(name.partition(".")[0] for name in APPLICATION_CONSTRUCTORS)
DJANGO_APP_MODULES = ("apps", "models", "admin")
"""Modules of an installed application that Django imports when it starts."""
DJANGO_APP_PACKAGES = ("management.commands", "templatetags")
"""Packages of an installed application whose modules Django loads by name on demand."""
_TEST_DIRECTORIES = frozenset({"test", "testing", "tests"})
_NON_LIBRARY_DIRECTORIES = frozenset({"benchmarks", "docs", "examples", *_TEST_DIRECTORIES})


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


@dataclass(slots=True)
class _BuildState:
    program: PythonProgram
    config: Config
    entry_points: tuple[ProjectEntryPoint, ...] = ()
    entry_point_issues: tuple[EntryPointIssue, ...] = ()
    objects: dict[str, FrameworkObject] = field(default_factory=dict)
    routes: list[RouteRegistration] = field(default_factory=list)
    hooks: list[FrameworkHook] = field(default_factory=list)
    includes: list[RouterInclude] = field(default_factory=list)
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
    timings: StageTimings | None = None,
) -> FrameworkModel:
    """Apply built-in framework capabilities and construct isolated world plans."""

    timings = timings if timings is not None else StageTimings()
    state = _BuildState(
        program=program,
        config=config,
        entry_points=entry_points,
        entry_point_issues=entry_point_issues,
    )
    with timings.stage("frontend.frameworks_discover"):
        _discover_provider_bindings(state)
        _discover_objects(state)
        _discover_uncalled_fastapi_factories(state)
        _index_object_keys(state)
        _discover_factory_assembly(state)
        _discover_routes(state)
        _discover_includes_and_setup(state)
        _discover_migration_contracts(state)
        _discover_application_factories(state)
        _discover_task_autodiscovery(state)
        _discover_django_applications(state)
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
        capabilities=(
            FrameworkCapability("python.direct-flow", 5, "modeled"),
            FrameworkCapability("fastapi.routes", 2, "modeled"),
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
            FrameworkCapability("django.migrations-runpython", 1, "modeled"),
            FrameworkCapability("python.project-entry-points", 1, "modeled"),
            FrameworkCapability("python.script-roots", 1, "modeled"),
            FrameworkCapability("python.library-roots", 1, "modeled"),
            FrameworkCapability("frameworks.application-roots", 1, "guarded"),
            FrameworkCapability("celery.autodiscover-tasks", 1, "guarded"),
            FrameworkCapability("django.installed-apps", 1, "modeled"),
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
            elif function_name in APPLICATION_CONSTRUCTORS:
                state.applications[key] = (APPLICATION_CONSTRUCTORS[function_name], module.name)
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
        if not any(
            binding.target.partition(".")[0] == "fastapi" for binding in module.imports.values()
        ):
            continue
        for factory in module.symbols:
            if (
                factory.owner is not None
                or not is_function(factory)
                or factory.id in state.app_factories
            ):
                continue
            factory_app = _fastapi_factory_app(state, factory)
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


def _discover_migration_contracts(state: _BuildState) -> None:
    """Retain RunPython callbacks as external historical execution contracts."""

    for module in state.program.modules.values():
        path_parts = module.path.replace("\\", "/").split("/")
        if "migrations" not in path_parts:
            continue
        _discover_module_migration_contracts(state, module)


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
    expressions = positional_arguments(call)[:2]
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
                if object_key is None:
                    assembly = AssemblyState.INVALID
                    limitations.append(
                        Limitation(
                            code="DT3001",
                            message=f"configured root cannot be resolved: {root}",
                            world=world_id,
                        )
                    )
                    continue
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
        retained.update(state.migration_callbacks)
        retained.update(state.migration_declarations)
        conservative.update(state.migration_callbacks)
        conservative.update(state.migration_declarations)
        for module_name in sorted(state.unknown_migration_modules):
            module = state.program.modules[module_name]
            conservative.add(module.node_id)
            if assembly is not AssemblyState.INVALID:
                assembly = AssemblyState.PARTIAL
            limitations.append(
                Limitation(
                    code="DT3301",
                    message=f"Django RunPython callback cannot be resolved in {module.path}",
                    origin=module.node_id,
                    world=world_id,
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
            )
        )
    return tuple(sorted(plans, key=lambda item: item.id))


def _auto_worlds(state: _BuildState) -> tuple[WorldConfig, ...]:
    apps = sorted(
        obj.key for obj in state.objects.values() if obj.kind is FrameworkObjectKind.FASTAPI_APP
    )
    entry_worlds = tuple(
        WorldConfig(
            profile="production",
            scenario=entry_point.scenario,
            roots=(entry_point.target,),
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
    if not worlds:
        worlds.extend(_library_world(state))
    worlds.extend(_script_world(state))
    if not worlds:
        return (WorldConfig("production", "application", ("<auto>",)),)
    return tuple(worlds)


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
        if not _is_test_module(module)
        and (name.rpartition(".")[2] == "__main__" or has_main_guard(module))
    )
    for name in scripts:
        state.auto_provenance[("scripts", name)] = ("main_module", name)
    return (WorldConfig("production", "scripts", tuple(scripts), ("python",)),) if scripts else ()


def _library_world(state: _BuildState) -> tuple[WorldConfig, ...]:
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
        roots[name] = None
        exports = declared_exports(module) or frozenset()
        is_package = module.path.endswith("__init__.py")
        api = [
            symbol
            for symbol in module.symbols
            if symbol.owner is None and (not symbol.name.startswith("_") or symbol.name in exports)
        ]
        for binding in module.imports.values():
            public = is_package and not binding.local_name.startswith("_")
            target = (
                program.resolve_symbol(binding.target)
                if public or binding.local_name in exports
                else None
            )
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


def _is_test_module(module: PythonModule) -> bool:
    *directories, file_name = module.path.split("/")
    return (
        any(directory in _TEST_DIRECTORIES for directory in directories)
        or file_name.startswith("test_")
        or file_name.endswith("_test.py")
        or file_name == "conftest.py"
    )


def _is_non_library_module(module: PythonModule) -> bool:
    directories = module.path.split("/")[:-1]
    return _is_test_module(module) or any(
        directory in _NON_LIBRARY_DIRECTORIES for directory in directories
    )


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
                        if symbol.owner is None and symbol.kind is NodeKind.CLASS
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
) -> tuple[str, ast.Call] | None:
    """Recognize one local FastAPI construction that is returned unchanged."""

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
    return state.object_keys.get(_expanded_name(module, expression))


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
