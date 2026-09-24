from __future__ import annotations

from pathlib import Path

from deadtrace.core import NodeId, ReachabilityKind, WorldId, WorldPlan, solve
from deadtrace.python_frontend import PythonProgram, PythonSymbol, build_python_program
from deadtrace.scanner import SourceCollection, SourceUnit


def _collection(**sources: str) -> SourceCollection:
    return SourceCollection(
        root=Path("/project"),
        files=tuple(sorted(sources)),
        units=tuple(
            SourceUnit(path, Path("/project") / path, source, f"digest-{path}")
            for path, source in sorted(sources.items())
        ),
        issues=(),
    )


def _id(program: PythonProgram, target: str) -> NodeId:
    symbol = program.resolve_symbol(target)
    assert symbol is not None, target
    return symbol.id


def test_symbol_index_answers_exactly_what_a_scan_of_the_symbol_table_returns() -> None:
    program = build_python_program(
        _collection(
            **{
                "shop.py": """
class Cart:
    def add(self) -> None:
        pass

    def add(self) -> None:
        pass

    class Line:
        def total(self) -> int:
            return 0

def Cart() -> None:
    pass

def cartesian() -> None:
    pass
""",
                "shop_extra.py": "def helper() -> None:\n    pass\n",
            }
        )
    )
    symbols = list(program.symbols.values())

    def full_name(symbol: PythonSymbol) -> str:
        return f"{symbol.module}.{symbol.qualified_name}"

    for name in sorted({full_name(symbol) for symbol in symbols} | {"shop.Missing"}):
        matches = [symbol for symbol in symbols if full_name(symbol) == name]
        best = max(matches, key=lambda symbol: symbol.occurrence, default=None)
        assert [symbol.id for symbol in program.index.named(name)] == [s.id for s in matches]
        resolved = program.index.resolve(name)
        assert (resolved.id if resolved else None) == (best.id if best else None)
    for owner in {symbol.owner for symbol in symbols if symbol.owner is not None}:
        assert [symbol.id for symbol in program.index.members(owner)] == [
            symbol.id for symbol in symbols if symbol.owner == owner
        ]
    for prefix in ("shop.Cart", "shop.Cart.", "shop", "shop_", "missing"):
        assert sorted(symbol.id for symbol in program.index.under(prefix)) == sorted(
            symbol.id for symbol in symbols if full_name(symbol).startswith(prefix)
        )
    tied = program.resolve_symbol("shop:Cart")
    assert tied is not None and tied.kind.value == "class"


def test_import_constructor_field_and_method_flow() -> None:
    program = build_python_program(
        _collection(
            **{
                "repo.py": """
class Repository:
    def load(self) -> str:
        return "dish"
""",
                "service.py": """
from repo import Repository

class Service:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def get(self) -> str:
        return self.repository.load()
""",
                "entry.py": """
from repo import Repository
from service import Service

def entry() -> str:
    repository = Repository()
    service = Service(repository)
    return service.get()
""",
            }
        )
    )
    world = WorldId("production", "service")
    entry = _id(program, "entry:entry")

    result = solve(
        program.graph,
        (WorldPlan(world, (NodeId("py-module:entry"), entry)),),
    ).world(world)

    expected = {
        "repo:Repository",
        "repo:Repository.load",
        "service:Service",
        "service:Service.__init__",
        "service:Service.get",
    }
    assert {target for target in expected if result.state_of(_id(program, target)) is None} == set()


def test_same_method_names_resolve_by_receiver_type() -> None:
    program = build_python_program(
        _collection(
            **{
                "case.py": """
class First:
    def run(self) -> None:
        pass

class Second:
    def run(self) -> None:
        pass

def entry(first: First) -> None:
    first.run()
"""
            }
        )
    )
    world = WorldId("production", "service")

    result = solve(
        program.graph,
        (WorldPlan(world, (_id(program, "case:entry"),)),),
    ).world(world)

    assert result.state_of(_id(program, "case:First.run")) is not None
    assert result.state_of(_id(program, "case:Second.run")) is None


def test_dynamic_getattr_is_localized_to_receiver_class() -> None:
    program = build_python_program(
        _collection(
            **{
                "case.py": """
class Service:
    def first(self) -> None:
        pass

    def second(self) -> None:
        pass

def dynamic(service: Service, name: str) -> None:
    getattr(service, name)()

def unrelated() -> None:
    pass
"""
            }
        )
    )
    world = WorldId("production", "service")

    result = solve(
        program.graph,
        (WorldPlan(world, (_id(program, "case:dynamic"),)),),
    ).world(world)

    assert _id(program, "case:Service.first") in result.conservative_may_run
    assert _id(program, "case:Service.second") in result.conservative_may_run
    assert result.state_of(_id(program, "case:unrelated")) is None


def test_unknown_operation_in_unreachable_body_does_not_guard_project() -> None:
    program = build_python_program(
        _collection(
            **{
                "case.py": """
def entry() -> None:
    pass

def dynamic(obj: object, name: str) -> None:
    getattr(obj, name)()

def candidate() -> None:
    pass
"""
            }
        )
    )
    world = WorldId("production", "service")

    result = solve(
        program.graph,
        (WorldPlan(world, (_id(program, "case:entry"),)),),
    ).world(world)

    assert result.state_of(_id(program, "case:dynamic")) is None
    assert result.state_of(_id(program, "case:candidate")) is None


def test_callable_argument_flow_reaches_callback_and_helper() -> None:
    program = build_python_program(
        _collection(
            **{
                "case.py": """
def invoke(callback):
    callback()

def helper() -> None:
    pass

def callback() -> None:
    helper()

def entry() -> None:
    invoke(callback)
"""
            }
        )
    )
    world = WorldId("production", "callback")

    result = solve(
        program.graph,
        (WorldPlan(world, (_id(program, "case:entry"),)),),
    ).world(world)

    assert result.state_of(_id(program, "case:invoke")) is not None
    assert result.state_of(_id(program, "case:callback")) is not None
    assert result.state_of(_id(program, "case:helper")) is not None


def test_later_local_definition_shadows_import() -> None:
    program = build_python_program(
        _collection(
            **{
                "external.py": """
def helper() -> None:
    pass
""",
                "case.py": """
from external import helper

def helper() -> None:
    pass

def entry() -> None:
    helper()
""",
            }
        )
    )
    world = WorldId("production", "shadow")

    result = solve(
        program.graph,
        (WorldPlan(world, (_id(program, "case:entry"),)),),
    ).world(world)

    assert result.state_of(_id(program, "case:helper")) is not None
    assert result.state_of(_id(program, "external:helper")) is None


def test_later_import_shadows_local_definition() -> None:
    program = build_python_program(
        _collection(
            **{
                "external.py": "def helper() -> None:\n    pass\n",
                "case.py": """
def helper() -> None:
    pass

from external import helper

def entry() -> None:
    helper()
""",
            }
        )
    )
    world = WorldId("production", "shadow")

    result = solve(
        program.graph,
        (WorldPlan(world, (_id(program, "case:entry"),)),),
    ).world(world)

    assert result.state_of(_id(program, "external:helper")) is not None
    assert result.state_of(_id(program, "case:helper")) is None


def test_relative_import_module_alias_and_annotated_local_flow() -> None:
    program = build_python_program(
        _collection(
            **{
                "pkg/__init__.py": "",
                "pkg/repo.py": """
class Repository:
    def load(self) -> None:
        pass
""",
                "pkg/service.py": """
from . import repo

def entry() -> None:
    repository: repo.Repository = repo.Repository()
    repository.load()
""",
            }
        )
    )
    world = WorldId("production", "relative")

    result = solve(
        program.graph,
        (WorldPlan(world, (_id(program, "pkg.service:entry"),)),),
    ).world(world)

    assert result.state_of(_id(program, "pkg.repo:Repository")) is not None
    assert result.state_of(_id(program, "pkg.repo:Repository.load")) is not None


def test_callable_escaping_to_external_consumer_is_conservative() -> None:
    program = build_python_program(
        _collection(
            **{
                "case.py": """
from external_runtime import register

def helper() -> None:
    pass

def callback() -> None:
    helper()

def entry() -> None:
    register(callback)
"""
            }
        )
    )
    world = WorldId("production", "callback")

    result = solve(
        program.graph,
        (WorldPlan(world, (_id(program, "case:entry"),)),),
    ).world(world)

    assert _id(program, "case:callback") in result.conservative_may_run
    assert _id(program, "case:helper") in result.conservative_may_run


def test_unlocalized_dynamic_dispatch_protects_whole_graph() -> None:
    program = build_python_program(
        _collection(
            **{
                "case.py": """
def dynamic(obj: object, name: str) -> None:
    getattr(obj, name)()

def otherwise_candidate() -> None:
    pass
"""
            }
        )
    )
    world = WorldId("production", "dynamic")

    result = solve(
        program.graph,
        (WorldPlan(world, (_id(program, "case:dynamic"),)),),
    ).world(world)

    assert _id(program, "case:otherwise_candidate") in result.conservative_may_run


def test_property_and_protocol_hooks_guard_transitive_helpers() -> None:
    program = build_python_program(
        _collection(
            **{
                "main.py": """
class Resource:
    @property
    def value(self) -> str:
        return property_helper()

    def __iter__(self):
        protocol_helper()
        return iter(())

def property_helper() -> str:
    return "value"

def protocol_helper() -> None:
    pass

def root() -> Resource:
    return Resource()
"""
            }
        )
    )
    world = WorldId("production", "web")
    result = solve(
        program.graph,
        (WorldPlan(world, (_id(program, "main:root"),)),),
    ).world(world)

    for target in (
        "main:Resource.value",
        "main:property_helper",
        "main:Resource.__iter__",
        "main:protocol_helper",
    ):
        assert result.state_of(_id(program, target)) is ReachabilityKind.CONSERVATIVE
    assert any(limit.code == "DT2002" for limit in result.limitations)


def test_project_metaclass_hooks_are_guarded_from_module_execution() -> None:
    program = build_python_program(
        _collection(
            **{
                "main.py": """
def metaclass_helper() -> None:
    pass

class Meta(type):
    def __new__(mcls, name, bases, namespace):
        metaclass_helper()
        return super().__new__(mcls, name, bases, namespace)

class Resource(metaclass=Meta):
    pass
"""
            }
        )
    )
    world = WorldId("production", "import")
    result = solve(
        program.graph,
        (WorldPlan(world, (program.modules["main"].node_id,)),),
    ).world(world)

    assert result.state_of(_id(program, "main:Meta.__new__")) is ReachabilityKind.CONSERVATIVE
    assert result.state_of(_id(program, "main:metaclass_helper")) is ReachabilityKind.CONSERVATIVE


def test_decorators_defaults_and_local_imports_are_declaration_effects() -> None:
    program = build_python_program(
        _collection(
            **{
                "dependency.py": "def imported():\n    pass\n",
                "main.py": """
from dependency import imported

def decorate():
    return lambda function: function

def default_factory():
    return object()

@decorate()
def declared(value=default_factory()):
    return value
""",
            }
        )
    )
    world = WorldId("production", "import")
    result = solve(
        program.graph,
        (WorldPlan(world, (program.modules["main"].node_id,)),),
    ).world(world)

    assert result.state_of(_id(program, "main:decorate")) is ReachabilityKind.RESOLVED
    assert result.state_of(_id(program, "main:default_factory")) is ReachabilityKind.RESOLVED
    assert result.state_of(program.modules["dependency"].node_id) is ReachabilityKind.RESOLVED
