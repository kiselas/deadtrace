from __future__ import annotations

from pathlib import Path

from deadtrace.config import Config, KeepConfig, WorldConfig
from deadtrace.core import AssemblyState, NodeId, WorldId, solve
from deadtrace.frameworks import build_framework_model
from deadtrace.python_frontend import PythonProgram, build_python_program
from deadtrace.scanner import SourceCollection, SourceUnit


def _program(**sources: str) -> PythonProgram:
    collection = SourceCollection(
        root=Path("/project"),
        files=tuple(sorted(sources)),
        units=tuple(
            SourceUnit(path, Path("/project") / path, source, f"digest-{path}")
            for path, source in sorted(sources.items())
        ),
        issues=(),
    )
    return build_python_program(collection)


def _id(program: PythonProgram, target: str) -> NodeId:
    symbol = program.resolve_symbol(target)
    assert symbol is not None, target
    return symbol.id


def _reference_sources(*, injected: bool = True) -> dict[str, str]:
    inject_decorator = "@inject\n" if injected else ""
    return {
        "repo.py": """
class Repository:
    def load(self) -> str:
        return "dish"
""",
        "services.py": """
from repo import Repository

def normalize(value: str) -> str:
    return value.strip()

class Service:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def get(self) -> str:
        return normalize(self.repository.load())

class LegacyService:
    def run(self) -> str:
        return normalize("legacy")
""",
        "providers.py": """
from dishka import Provider, Scope, provide
from repo import Repository
from services import LegacyService, Service

class AppProvider(Provider):
    @provide(scope=Scope.REQUEST)
    def repository(self) -> Repository:
        return Repository()

    @provide(scope=Scope.REQUEST)
    def service(self, repository: Repository) -> Service:
        return Service(repository)

    @provide(scope=Scope.REQUEST)
    def legacy(self) -> LegacyService:
        return LegacyService()
""",
        "routes.py": f"""
from fastapi import APIRouter
from dishka.integrations.fastapi import FromDishka, inject
from services import Service

router = APIRouter()

@router.get("/dish")
{inject_decorator}async def endpoint(service: FromDishka[Service]) -> str:
    return service.get()
""",
        "main.py": """
from fastapi import FastAPI
from dishka import make_async_container
from dishka.integrations.fastapi import setup_dishka
from providers import AppProvider
from routes import router

app = FastAPI()
app.include_router(router)
container = make_async_container(AppProvider())
setup_dishka(container=container, app=app)
""",
    }


def test_fastapi_dishka_reference_chain_and_unrequested_binding() -> None:
    program = _program(**_reference_sources())
    model = build_framework_model(program, Config())
    assert len(model.plans) == 1

    result = solve(model.graph, model.plans).world(model.plans[0].id)

    for target in (
        "routes:endpoint",
        "providers:AppProvider.service",
        "providers:AppProvider.repository",
        "services:Service",
        "services:Service.get",
        "repo:Repository",
        "repo:Repository.load",
        "services:normalize",
    ):
        assert result.state_of(_id(program, target)) is not None, target
    legacy_factory = _id(program, "providers:AppProvider.legacy")
    assert result.state_of(legacy_factory) is None
    assert legacy_factory in result.retained
    assert result.state_of(_id(program, "services:LegacyService")) is None
    assert result.negative_findings_allowed


def test_inactive_dishka_integration_blocks_negative_gate_and_guards_demand() -> None:
    program = _program(**_reference_sources(injected=False))
    model = build_framework_model(program, Config())

    result = solve(model.graph, model.plans).world(model.plans[0].id)

    assert result.assembly_state is AssemblyState.PARTIAL
    # The endpoint annotation uses Service; the guard covers the unresolved binding.
    assert result.state_of(_id(program, "services:Service")) is not None
    assert result.state_of(_id(program, "providers:AppProvider.service")) is None
    assert not result.negative_findings_allowed
    assert any(limit.code == "DT3101" for limit in result.limitations)


def test_fastapi_depends_runs_even_when_return_value_is_unused() -> None:
    program = _program(
        **{
            "main.py": """
from typing import Annotated
from fastapi import Depends, FastAPI

def token() -> str:
    return "token"

def auth(value: Annotated[str, Depends(token)]) -> None:
    pass

app = FastAPI()

@app.get("/", dependencies=[Depends(auth)])
def endpoint() -> str:
    return "ok"
"""
        }
    )
    model = build_framework_model(program, Config())

    result = solve(model.graph, model.plans).world(model.plans[0].id)

    assert result.state_of(_id(program, "main:endpoint")) is not None
    assert result.state_of(_id(program, "main:auth")) is not None
    assert result.state_of(_id(program, "main:token")) is not None


def test_unincluded_router_is_not_an_execution_root() -> None:
    program = _program(
        **{
            "routes.py": """
from fastapi import APIRouter

router = APIRouter()

@router.get("/hidden")
def hidden_endpoint() -> None:
    pass
""",
            "main.py": """
from fastapi import FastAPI

app = FastAPI()
""",
        }
    )
    model = build_framework_model(program, Config())

    result = solve(model.graph, model.plans).world(model.plans[0].id)

    assert result.state_of(_id(program, "routes:hidden_endpoint")) is None


def test_two_apps_have_isolated_route_worlds() -> None:
    program = _program(
        **{
            "main.py": """
from fastapi import FastAPI

first = FastAPI()
second = FastAPI()

@first.get("/first")
def first_endpoint() -> None:
    pass

@second.get("/second")
def second_endpoint() -> None:
    pass
"""
        }
    )
    model = build_framework_model(program, Config())

    snapshot = solve(model.graph, model.plans)
    first_plan = next(plan for plan in model.plans if plan.id.scenario.endswith("main.first"))
    second_plan = next(plan for plan in model.plans if plan.id.scenario.endswith("main.second"))

    assert snapshot.world(first_plan.id).state_of(_id(program, "main:first_endpoint")) is not None
    assert snapshot.world(first_plan.id).state_of(_id(program, "main:second_endpoint")) is None
    assert snapshot.world(second_plan.id).state_of(_id(program, "main:second_endpoint")) is not None
    assert snapshot.world(second_plan.id).state_of(_id(program, "main:first_endpoint")) is None


def test_explicit_invalid_root_is_not_clean() -> None:
    program = _program(**{"case.py": "def candidate():\n    pass\n"})
    config = Config(worlds=(WorldConfig("production", "web", ("missing:app",)),))
    model = build_framework_model(program, config)

    result = solve(model.graph, model.plans).world(model.plans[0].id)

    assert result.assembly_state is AssemblyState.INVALID
    assert not result.negative_findings_allowed
    assert any(limit.code == "DT3001" for limit in result.limitations)


def test_dishka_route_enables_injection_without_decorator() -> None:
    sources = _reference_sources(injected=False)
    sources["routes.py"] = """
from fastapi import APIRouter
from dishka.integrations.fastapi import DishkaRoute, FromDishka
from services import Service

router = APIRouter(route_class=DishkaRoute)

@router.get("/dish")
async def endpoint(service: FromDishka[Service]) -> str:
    return service.get()
"""
    program = _program(**sources)
    model = build_framework_model(program, Config())

    result = solve(model.graph, model.plans).world(model.plans[0].id)

    assert result.assembly_state is AssemblyState.COMPLETE
    assert result.state_of(_id(program, "providers:AppProvider.service")) is not None


def test_missing_setup_or_endpoint_binding_limits_world() -> None:
    no_setup = _reference_sources()
    no_setup["main.py"] = no_setup["main.py"].replace(
        "setup_dishka(container=container, app=app)", ""
    )
    program = _program(**no_setup)
    model = build_framework_model(program, Config())
    result = solve(model.graph, model.plans).world(model.plans[0].id)
    assert any(limit.code == "DT3102" for limit in result.limitations)
    assert result.assembly_state is AssemblyState.PARTIAL

    missing = _reference_sources()
    missing["providers.py"] = missing["providers.py"].replace(
        "    @provide(scope=Scope.REQUEST)\n"
        "    def service(self, repository: Repository) -> Service:\n"
        "        return Service(repository)\n\n",
        "",
    )
    program = _program(**missing)
    model = build_framework_model(program, Config())
    result = solve(model.graph, model.plans).world(model.plans[0].id)
    assert any(limit.code == "DT3103" for limit in result.limitations)
    assert result.assembly_state is AssemblyState.PARTIAL


def test_missing_nested_provider_dependency_limits_world() -> None:
    sources = _reference_sources()
    sources["providers.py"] = sources["providers.py"].replace(
        "    @provide(scope=Scope.REQUEST)\n"
        "    def repository(self) -> Repository:\n"
        "        return Repository()\n\n",
        "",
    )
    program = _program(**sources)
    model = build_framework_model(program, Config())

    result = solve(model.graph, model.plans).world(model.plans[0].id)

    assert any(limit.code == "DT3104" for limit in result.limitations)
    assert result.assembly_state is AssemblyState.PARTIAL


def test_explicit_router_root_container_rejection_and_external_keeps() -> None:
    program = _program(**_reference_sources())
    router_config = Config(
        worlds=(WorldConfig("production", "router", ("routes:router",)),),
        keep=(KeepConfig("services:LegacyService", "external API", ("production",)),),
    )
    router_model = build_framework_model(program, router_config)
    router_result = solve(router_model.graph, router_model.plans).world(router_model.plans[0].id)
    assert _id(program, "services:LegacyService") in router_result.retained

    container_config = Config(
        worlds=(WorldConfig("production", "bad", ("main:container",)),),
        keep=(KeepConfig("missing:hook", "external", ("production",)),),
    )
    container_model = build_framework_model(program, container_config)
    container_result = solve(container_model.graph, container_model.plans).world(
        container_model.plans[0].id
    )
    assert container_result.assembly_state is AssemblyState.INVALID
    assert any(limit.code == "DT3002" for limit in container_result.limitations)
    assert any(limit.code == "DT3003" for limit in container_result.limitations)


def test_fastapi_lifespan_background_task_and_pydantic_hooks_are_live() -> None:
    program = _program(
        **{
            "main.py": """
from contextlib import asynccontextmanager
from fastapi import BackgroundTasks, FastAPI
from pydantic import BaseModel, field_validator

def cleanup_helper() -> None:
    pass

def background_job() -> None:
    pass

def validation_helper() -> None:
    pass

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    cleanup_helper()

class Payload(BaseModel):
    value: str

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: str) -> str:
        validation_helper()
        return value

app = FastAPI(lifespan=lifespan)

@app.post("/")
def endpoint(payload: Payload, tasks: BackgroundTasks) -> Payload:
    tasks.add_task(background_job)
    return payload
"""
        }
    )
    model = build_framework_model(program, Config())

    result = solve(model.graph, model.plans).world(model.plans[0].id)

    for target in (
        "main:lifespan",
        "main:cleanup_helper",
        "main:background_job",
        "main:Payload",
        "main:Payload.validate_value",
        "main:validation_helper",
    ):
        assert result.state_of(_id(program, target)) is not None, target
    assert not any("add_task" in limitation.message for limitation in result.limitations)


def test_dishka_from_context_request_and_explicit_context() -> None:
    source = """
from fastapi import FastAPI, Request
from dishka import Provider, Scope, from_context, make_async_container, provide
from dishka.integrations.fastapi import FastapiProvider, FromDishka, inject, setup_dishka

class Config:
    pass

class Service:
    def __init__(self, request: Request, config: Config) -> None:
        self.request = request
        self.config = config

class AppProvider(Provider):
    request = from_context(provides=Request, scope=Scope.REQUEST)
    config = from_context(provides=Config, scope=Scope.APP, override=True)

    @provide(scope=Scope.REQUEST)
    def service(self, request: Request, config: Config) -> Service:
        return Service(request, config)

app = FastAPI()

@app.get("/")
@inject
def endpoint(service: FromDishka[Service]) -> None:
    pass

config = Config()
container = make_async_container(AppProvider(), FastapiProvider(), context={Config: config})
setup_dishka(container, app)
"""
    program = _program(**{"main.py": source})
    model = build_framework_model(program, Config())

    result = solve(model.graph, model.plans).world(model.plans[0].id)

    assert result.assembly_state is AssemblyState.COMPLETE
    assert len(model.context_bindings) == 2
    assert any(binding.override for binding in model.context_bindings)
    assert result.state_of(_id(program, "main:AppProvider.service")) is not None

    without_fastapi_provider = source.replace(
        "AppProvider(), FastapiProvider(), context=", "AppProvider(), context="
    )
    program = _program(**{"main.py": without_fastapi_provider})
    model = build_framework_model(program, Config())
    result = solve(model.graph, model.plans).world(model.plans[0].id)
    assert result.assembly_state is AssemblyState.PARTIAL
    assert any(limit.code == "DT3104" for limit in result.limitations)


def test_dishka_conditional_activation_guards_the_world() -> None:
    source = """
from dishka import Marker, Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import FromDishka, inject, setup_dishka
from fastapi import FastAPI

class Service:
    pass

class ProviderWithCondition(Provider):
    @provide(scope=Scope.REQUEST, when=Marker("enabled"))
    def service(self) -> Service:
        return Service()

app = FastAPI()

@app.get("/")
@inject
def endpoint(service: FromDishka[Service]) -> None:
    pass

container = make_async_container(ProviderWithCondition())
setup_dishka(container, app)
"""
    program = _program(**{"main.py": source})
    model = build_framework_model(program, Config())

    result = solve(model.graph, model.plans).world(model.plans[0].id)

    assert result.assembly_state is AssemblyState.PARTIAL
    assert not result.negative_findings_allowed
    assert any(limit.code == "DT3106" for limit in result.limitations)
    assert result.state_of(_id(program, "main:Service")) is not None
    assert _id(program, "main:ProviderWithCondition.service") in result.conservative_may_run


def test_bounded_app_factory_connects_router_and_container() -> None:
    source = """
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import FromDishka, inject, setup_dishka
from fastapi import APIRouter, FastAPI

class Service:
    pass

class AppProvider(Provider):
    @provide(scope=Scope.REQUEST)
    def service(self) -> Service:
        return Service()

router = APIRouter()

@router.get("/")
@inject
def endpoint(service: FromDishka[Service]) -> None:
    pass

container = make_async_container(AppProvider())

def create_app() -> FastAPI:
    application = FastAPI()
    application.include_router(router)
    setup_dishka(container, application)
    return application

app = create_app()
"""
    program = _program(**{"main.py": source})
    model = build_framework_model(program, Config())
    result = solve(model.graph, model.plans).world(model.plans[0].id)

    assert result.assembly_state is AssemblyState.COMPLETE
    assert result.state_of(_id(program, "main:endpoint")) is not None
    assert result.state_of(_id(program, "main:AppProvider.service")) is not None

    configured = build_framework_model(
        program,
        Config(worlds=(WorldConfig("production", "factory", ("main:create_app",)),)),
    )
    configured_result = solve(configured.graph, configured.plans).world(configured.plans[0].id)
    assert configured_result.state_of(_id(program, "main:endpoint")) is not None


def test_class_provider_and_alias_resolve_to_concrete_constructor() -> None:
    source = """
from dishka import Provider, Scope, alias, make_async_container, provide
from dishka.integrations.fastapi import FromDishka, inject, setup_dishka
from fastapi import FastAPI

class Repository:
    pass

class SqlRepository(Repository):
    pass

class Service:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

class AppProvider(Provider):
    repository = provide(SqlRepository, scope=Scope.REQUEST)
    repository_alias = alias(source=SqlRepository, provides=Repository)
    service = provide(Service, scope=Scope.REQUEST)

app = FastAPI()

@app.get("/")
@inject
def endpoint(service: FromDishka[Service]) -> None:
    pass

container = make_async_container(AppProvider())
setup_dishka(container, app)
"""
    program = _program(**{"main.py": source})
    model = build_framework_model(program, Config())
    result = solve(model.graph, model.plans).world(model.plans[0].id)

    assert result.assembly_state is AssemblyState.COMPLETE
    assert result.state_of(_id(program, "main:Service")) is not None
    assert result.state_of(_id(program, "main:Service.__init__")) is not None
    assert result.state_of(_id(program, "main:SqlRepository")) is not None
    assert not result.limitations


def test_two_apps_use_only_their_attached_dishka_container() -> None:
    source = """
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import FromDishka, inject, setup_dishka
from fastapi import FastAPI

class Service:
    pass

class FirstProvider(Provider):
    @provide(scope=Scope.REQUEST)
    def service(self) -> Service:
        return Service()

class SecondProvider(Provider):
    @provide(scope=Scope.REQUEST)
    def service(self) -> Service:
        return Service()

first = FastAPI()
second = FastAPI()

@first.get("/first")
@inject
def first_endpoint(service: FromDishka[Service]) -> None:
    pass

@second.get("/second")
@inject
def second_endpoint(service: FromDishka[Service]) -> None:
    pass

first_container = make_async_container(FirstProvider())
second_container = make_async_container(SecondProvider())
setup_dishka(first_container, first)
setup_dishka(second_container, second)
"""
    program = _program(**{"main.py": source})
    model = build_framework_model(program, Config())
    snapshot = solve(model.graph, model.plans)
    first = snapshot.world(WorldId("production", "web:main.first"))
    second = snapshot.world(WorldId("production", "web:main.second"))

    first_factory = _id(program, "main:FirstProvider.service")
    second_factory = _id(program, "main:SecondProvider.service")
    assert first.state_of(first_factory) is not None
    assert first.state_of(second_factory) is None
    assert second.state_of(second_factory) is not None
    assert second.state_of(first_factory) is None


def test_dishka_components_are_guarded_until_binding_selection_is_modeled() -> None:
    source = """
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import FromDishka, inject, setup_dishka
from fastapi import FastAPI

class Service:
    pass

class ComponentProvider(Provider):
    component = "billing"

    @provide(scope=Scope.REQUEST)
    def service(self) -> Service:
        return Service()

app = FastAPI()

@app.get("/")
@inject
def endpoint(service: FromDishka[Service]) -> None:
    pass

container = make_async_container(ComponentProvider())
setup_dishka(container, app)
"""
    program = _program(**{"main.py": source})
    model = build_framework_model(program, Config())
    result = solve(model.graph, model.plans).world(model.plans[0].id)

    assert result.assembly_state is AssemblyState.PARTIAL
    assert any(limit.code == "DT3107" for limit in result.limitations)
    assert _id(program, "main:ComponentProvider.service") in result.conservative_may_run


def test_django_runpython_callback_is_a_conservative_external_contract() -> None:
    program = _program(
        **{
            "main.py": "from fastapi import FastAPI\napp = FastAPI()\n",
            "app/migrations/0001_data.py": """
from django.db import migrations

def helper() -> None:
    pass

def forwards(apps, schema_editor) -> None:
    helper()

class Migration(migrations.Migration):
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
""",
        }
    )
    model = build_framework_model(program, Config())
    result = solve(model.graph, model.plans).world(model.plans[0].id)

    assert _id(program, "app.migrations.0001_data:forwards") in result.retained
    assert _id(program, "app.migrations.0001_data:forwards") in result.conservative_may_run
    assert _id(program, "app.migrations.0001_data:helper") in result.conservative_may_run
    assert _id(program, "app.migrations.0001_data:Migration") in result.retained


def test_unresolved_django_migration_callback_blocks_negative_gate() -> None:
    program = _program(
        **{
            "main.py": "from fastapi import FastAPI\napp = FastAPI()\n",
            "app/migrations/0002_dynamic.py": """
from django.db import migrations

callback = load_callback()

class Migration(migrations.Migration):
    operations = [migrations.RunPython(callback)]
""",
        }
    )
    model = build_framework_model(program, Config())
    result = solve(model.graph, model.plans).world(model.plans[0].id)

    assert result.assembly_state is AssemblyState.PARTIAL
    assert any(limit.code == "DT3301" for limit in result.limitations)
    assert not result.negative_findings_allowed


def test_a_modeled_dependency_class_does_not_expose_its_methods() -> None:
    program = _program(
        **{
            "main.py": """
from fastapi import Depends, FastAPI

class Service:
    def run(self) -> str:
        return "ok"

    def unused(self) -> None:
        pass

app = FastAPI()

@app.get("/")
def endpoint(service: Service = Depends(Service)) -> str:
    return service.run()
"""
        }
    )
    model = build_framework_model(program, Config())
    result = solve(model.graph, model.plans).world(model.plans[0].id)

    assert not any(boundary.domain == "escaped_class" for boundary in model.graph.boundaries)
    assert result.state_of(_id(program, "main:Service.run")) is not None
    assert result.state_of(_id(program, "main:Service.unused")) is None
