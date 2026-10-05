"""Automatic worlds (ADR-0011): what each discovers, and what it must leave alone.

The positive cases live in ``corpus/``. These tests pin the discovery rules and their limits.
"""

from __future__ import annotations

import ast
from itertools import pairwise
from pathlib import Path

import pytest

from deadtrace.config import Config, WorldConfig
from deadtrace.core import (
    EdgeKind,
    ExecutionEdge,
    NodeId,
    NodeKind,
    SemanticGraph,
    SemanticNode,
    WorldId,
    WorldPlan,
    solve,
)
from deadtrace.frameworks import FrameworkModel, build_framework_model
from deadtrace.python_frontend import (
    PythonModule,
    PythonProgram,
    build_python_program,
    declared_exports,
    has_main_guard,
)
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


def _model(**sources: str) -> tuple[PythonProgram, FrameworkModel]:
    program = _program(**sources)
    return program, build_framework_model(program, Config())


def _module(source: str) -> PythonModule:
    return _program(**{"module.py": source}).modules["module"]


def _public_objects_sources(
    field: str = "self.trace: Wrapper = Wrapper(Trace())",
) -> dict[str, str]:
    return {
        "pkg/__init__.py": "from ._api import Manager as Manager\n",
        "pkg/_api.py": (
            "from typing import Final\nfrom ._objects import Trace, Wrapper\n"
            f"class Manager:\n    def __init__(self):\n        {field}\n"
        ),
        "pkg/_objects.py": (
            "class Trace:\n    def setwriter(self, writer): pass\n"
            "    def _unused(self): pass\n"
            "class Wrapper:\n    def __init__(self, root: Trace):\n        self.root = root\n"
            "class Unrelated:\n    def configure(self): pass\n"
        ),
    }


@pytest.mark.parametrize(
    "field",
    [
        "self.trace: Wrapper = Wrapper(Trace())",
        "self.trace: Final[Wrapper] = factory()",
        "self.trace: 'Wrapper' = factory()",
    ],
)
def test_library_public_field_chain_exposes_methods(field: str) -> None:
    program, model = _model(**_public_objects_sources(field))
    plan = _plan(model, "production:library")
    exposed = program.resolve_symbol("pkg._objects:Trace.setwriter")
    private = program.resolve_symbol("pkg._objects:Trace._unused")
    unrelated = program.resolve_symbol("pkg._objects:Unrelated.configure")
    assert exposed is not None and exposed.id in plan.roots
    assert private is not None and private.id not in plan.roots
    assert unrelated is not None and unrelated.id not in plan.roots
    world = solve(model.graph, model.plans).world(plan.id)
    assert world.state_of(exposed.id) is not None
    assert world.state_of(private.id) is None
    assert world.state_of(unrelated.id) is None


def test_private_fields_do_not_expose_another_objects_api() -> None:
    program, model = _model(**_public_objects_sources("self._trace: Wrapper = factory()"))
    symbol = program.resolve_symbol("pkg._objects:Trace.setwriter")
    assert symbol is not None
    world = solve(model.graph, model.plans).world(WorldId("production", "library"))
    assert world.state_of(symbol.id) is None


def test_explicit_script_roots_do_not_expand_public_object_api() -> None:
    sources = _public_objects_sources()
    sources["main.py"] = "from pkg import Manager\ndef main():\n    return Manager()\n"
    program = _program(**sources)
    model = build_framework_model(
        program, Config(worlds=(WorldConfig("production", "script", ("main:main",), ("python",)),))
    )
    symbol = program.resolve_symbol("pkg._objects:Trace.setwriter")
    assert symbol is not None
    world = solve(model.graph, model.plans).world(WorldId("production", "script"))
    assert world.state_of(symbol.id) is None


def test_export_world_expands_public_fields_next_to_framework_application() -> None:
    sources = _public_objects_sources()
    sources["main.py"] = "from fastapi import FastAPI\napp = FastAPI()\n"
    program, model = _model(**sources)
    plan = _plan(model, "production:exports")
    exposed = program.resolve_symbol("pkg._objects:Trace.setwriter")
    assert exposed is not None and exposed.id in plan.roots


def test_private_project_base_exposes_inherited_public_methods_and_fields() -> None:
    sources = _public_objects_sources()
    sources["pkg/_api.py"] = (
        "from ._objects import Wrapper, Trace\n"
        "class Base:\n    def __init__(self):\n        self.trace: Wrapper = Wrapper(Trace())\n"
        "    def configure(self): pass\n    def _private(self): pass\n"
        "class Manager(Base): pass\n"
    )
    program, model = _model(**sources)
    plan = _plan(model, "production:library")
    for name in ("pkg._api:Base.configure", "pkg._objects:Trace.setwriter"):
        symbol = program.resolve_symbol(name)
        assert symbol is not None and symbol.id in plan.roots
    private = program.resolve_symbol("pkg._api:Base._private")
    assert private is not None
    assert solve(model.graph, model.plans).world(plan.id).state_of(private.id) is None


def test_cyclic_public_field_types_terminate_and_keep_both_apis() -> None:
    program, model = _model(
        **{
            "pkg/__init__.py": "from ._objects import First as First\n",
            "pkg/_objects.py": (
                "class First:\n    def __init__(self):\n        self.peer: 'Second' = factory()\n"
                "    def one(self): pass\n"
                "class Second:\n    def __init__(self):\n        self.peer: First = factory()\n"
                "    def two(self): pass\n"
            ),
        }
    )
    plan = _plan(model, "production:library")
    for name in ("pkg._objects:First.one", "pkg._objects:Second.two"):
        symbol = program.resolve_symbol(name)
        assert symbol is not None and symbol.id in plan.roots


@pytest.mark.parametrize(
    "annotation",
    ["Worker", "'Worker'", "Worker | None", "Maybe[Worker]", "Meta[Worker, Other]", "Worker[int]"],
)
def test_public_factory_return_contract_exposes_only_its_objects(annotation: str) -> None:
    program, model = _model(**_return_sources(annotation))
    plan = _plan(model, "production:library")
    for name in ("Worker.run", "Child.use"):
        symbol = program.resolve_symbol(f"pkg._objects:{name}")
        assert symbol is not None and symbol.id in plan.roots
    for name in ("Worker._unused", "Other.use"):
        symbol = program.resolve_symbol(f"pkg._objects:{name}")
        assert symbol is not None and symbol.id not in plan.roots


def _return_sources(annotation: str = "Worker") -> dict[str, str]:
    return {
        "pkg/__init__.py": "from ._api import make as make\n",
        "pkg/_api.py": (
            "from typing import Optional as Maybe, Annotated as Meta, Callable, Literal\n"
            "from ._objects import Worker, Other\n"
            f"def make(value: Other) -> {annotation}:\n    return factory()\n"
        ),
        "pkg/_objects.py": (
            "class Worker:\n    def run(self) -> 'Child': return factory()\n"
            "    def _unused(self) -> Other: return factory()\n"
            "class Child:\n    def use(self) -> Worker: return factory()\n"
            "class Other:\n    def use(self): pass\n"
        ),
    }


@pytest.mark.parametrize(
    "annotation", ["Callable[[Worker], None]", "Literal['Worker']", "list[Worker]"]
)
def test_annotation_mentions_are_not_direct_returned_objects(annotation: str) -> None:
    program, model = _model(**_return_sources(annotation))
    symbol = program.resolve_symbol("pkg._objects:Worker.run")
    assert symbol is not None and symbol.id not in _plan(model, "production:library").roots


def test_returned_objects_expand_fields_and_property_return_contracts() -> None:
    sources = _return_sources()
    sources["pkg/_objects.py"] = (
        "class Worker:\n    @property\n    def child(self) -> 'Child': return factory()\n"
        "class Child:\n    def __init__(self): self.other: Other = factory()\n"
        "class Other:\n    def use(self): pass\n"
    )
    program, model = _model(**sources)
    target = program.resolve_symbol("pkg._objects:Other.use")
    assert target is not None and target.id in _plan(model, "production:library").roots


def test_conditional_return_type_bindings_preserve_both_apis() -> None:
    sources = _return_sources()
    sources["pkg/_api.py"] = (
        "if choice:\n    from ._objects import Worker\n"
        "else:\n    from ._objects import Other as Worker\n"
        "def make() -> Worker: return factory()\n"
    )
    program, model = _model(**sources)
    plan = _plan(model, "production:library")
    for name in ("Worker.run", "Other.use"):
        symbol = program.resolve_symbol(f"pkg._objects:{name}")
        assert symbol is not None and symbol.id in plan.roots


def test_export_world_follows_factory_return_and_explicit_world_does_not() -> None:
    sources = _return_sources()
    sources["main.py"] = "from fastapi import FastAPI\napp = FastAPI()\n"
    program, model = _model(**sources)
    symbol = program.resolve_symbol("pkg._objects:Worker.run")
    assert symbol is not None and symbol.id in _plan(model, "production:exports").roots
    explicit = build_framework_model(
        program,
        Config(worlds=(WorldConfig("production", "script", ("pkg._api:make",), ("python",)),)),
    )
    assert symbol.id not in _plan(explicit, "production:script").roots


def _plan(model: FrameworkModel, key: str) -> WorldPlan:
    return next(plan for plan in model.plans if plan.id.key == key)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ('if __name__ == "__main__":\n    run()\n', True),
        ('if "__main__" == __name__:\n    run()\n', True),
        ('if __name__ != "__main__":\n    run()\n', False),
        ('if __name__ == "main":\n    run()\n', False),
        ('def run():\n    if __name__ == "__main__":\n        pass\n', False),
        ('if __name__ == "__main__" and ready:\n    run()\n', False),
    ],
)
def test_main_guard_is_a_top_level_equality_with_main(source: str, expected: bool) -> None:
    assert has_main_guard(_module(source)) is expected


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("x = 1\n", None),
        ('__all__ = ["a", "b"]\n', frozenset({"a", "b"})),
        ('__all__ = ("a",)\n__all__ += ["b"]\n', frozenset({"a", "b"})),
        ('__all__ = ["a"]\n__all__.append("b")\n__all__.extend(("c",))\n', frozenset("abc")),
        ('__all__: list[str] = ["a"]\n', frozenset({"a"})),
        ("__all__ = names()\n", None),
        ('__all__ = ["a", name]\n', None),
        ('__all__ += ["b"]\n', None),
        ('__all__ = ["a"]\n__all__.remove("a")\n', None),
        ('__all__ = ["a"]\n__all__ -= ["a"]\n', None),
    ],
)
def test_declared_exports_reads_only_literal_lists(
    source: str, expected: frozenset[str] | None
) -> None:
    assert declared_exports(_module(source)) == expected


def test_library_world_skips_private_test_and_example_modules() -> None:
    program, model = _model(
        **{
            "lib/__init__.py": "from lib._impl import helper\n",
            "lib/_impl.py": "def helper():\n    pass\n\ndef hidden():\n    pass\n",
            "lib/api.py": (
                "class Client:\n    def get(self):\n        pass\n\n"
                "    def _raw(self):\n        pass\n"
            ),
            "tests/test_api.py": "def test_client():\n    pass\n",
            "examples/demo.py": "def demo():\n    pass\n",
            "conftest.py": "def fixture():\n    pass\n",
        }
    )
    plan = _plan(model, "production:library")
    roots = {str(root) for root in plan.roots}

    assert {"py:lib._impl:helper:function:0", "py:lib.api:Client.get:function:0"} <= roots
    for private in ("lib._impl:hidden", "lib.api:Client._raw", "examples.demo:demo"):
        symbol = program.resolve_symbol(private)
        assert symbol is not None
        assert symbol.id not in plan.roots
    assert "py-module:tests.test_api" not in roots
    assert "py-module:conftest" not in roots
    kinds = {item.kind for item in plan.root_provenance}
    assert kinds == {"library_public_api"}


def test_library_world_needs_no_application_and_scripts_ignore_test_modules() -> None:
    _, model = _model(
        **{
            "app.py": "from fastapi import FastAPI\napp = FastAPI()\n",
            "tool.py": 'if __name__ == "__main__":\n    pass\n',
            "tests/test_tool.py": 'if __name__ == "__main__":\n    pass\n',
        }
    )
    keys = [plan.id.key for plan in model.plans]
    scripts = _plan(model, "production:scripts")

    assert keys == ["production:scripts", "production:web"]
    assert [str(root) for root in scripts.roots] == ["py-module:tool"]
    assert {item.kind for item in scripts.root_provenance} == {"main_module"}


def test_framework_applications_get_one_world_each() -> None:
    _, model = _model(
        **{
            "api.py": "from flask import Flask\napp = Flask(__name__)\nadmin = Flask('admin')\n",
            "worker.py": "import celery\napp = celery.Celery('worker')\n",
            "cli.py": "import typer\n\ndef build():\n    return typer.Typer()\n",
        }
    )
    keys = sorted(plan.id.key for plan in model.plans)
    cli = _plan(model, "production:typer")

    assert keys == [
        "production:celery",
        "production:flask:api.admin",
        "production:flask:api.app",
        "production:typer",
    ]
    assert [item.kind for item in cli.root_provenance] == ["framework_application"] * 2
    assert {item.detail for item in cli.root_provenance} == {"cli:build"}


def test_celery_autodiscovery_honors_related_name_and_needs_the_call() -> None:
    program, model = _model(
        **{
            "proj/celery.py": (
                "from celery import Celery\n"
                "app = Celery('proj')\n"
                "app.autodiscover_tasks(related_name='jobs')\n"
            ),
            "orders/jobs.py": "def job():\n    pass\n",
            "orders/tasks.py": "def task():\n    pass\n",
            "quiet/celery.py": "from celery import Celery\napp = Celery('quiet')\n",
        }
    )
    boundaries = [
        boundary for boundary in model.graph.boundaries if boundary.domain == "dynamic_import"
    ]

    assert len(boundaries) == 1
    assert boundaries[0].source == program.modules["proj.celery"].node_id
    assert boundaries[0].targets == (program.modules["orders.jobs"].node_id,)


def test_a_called_fastapi_factory_is_not_a_second_application() -> None:
    _, model = _model(
        **{
            "factory.py": (
                "from fastapi import FastAPI\n\n"
                "def create_app():\n"
                "    app = FastAPI()\n"
                "    return app\n"
            ),
            "main.py": "from factory import create_app\n\napp = create_app()\n",
        }
    )

    assert [plan.id.key for plan in model.plans] == ["production:web"]
    assert set(model.objects) == {"main:app"}


def test_projects_without_public_or_executable_code_stay_invalid() -> None:
    _, model = _model(**{"_internal.py": "def helper():\n    pass\n"})

    assert [plan.id.key for plan in model.plans] == ["production:application"]


def test_configured_worlds_replace_every_automatic_world() -> None:
    program = _program(
        **{
            "lib.py": "def api():\n    pass\n",
            "tool.py": 'if __name__ == "__main__":\n    pass\n',
        }
    )
    config = Config(worlds=(WorldConfig("production", "cli", ("tool",), ("python",)),))
    model = build_framework_model(program, config)

    assert [plan.id.key for plan in model.plans] == ["production:cli"]
    assert {item.kind for item in model.plans[0].root_provenance} == {"configured"}


def test_default_step_budget_covers_every_node_twice() -> None:
    names = [f"n{index}" for index in range(5)]
    graph = SemanticGraph(
        nodes=tuple(
            SemanticNode(NodeId(name), name, NodeKind.FUNCTION, "m.py", 1) for name in names
        ),
        edges=tuple(
            ExecutionEdge(NodeId(source), NodeId(target), EdgeKind.CALL, "call")
            for source, target in pairwise(names)
        ),
    )
    world = WorldId("production", "chain")
    plan = WorldPlan(
        world,
        (NodeId("n0"),),
        retained_roots=(),
        conservative_roots=tuple(NodeId(name) for name in names),
    )

    result = solve(graph, (plan,)).world(world)

    assert not result.exhausted_budget
    assert result.resolved_may_run == frozenset(NodeId(name) for name in names)


def test_type_checking_import_guard_is_not_mistaken_for_a_main_guard() -> None:
    module = _module("from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    import os\n")

    assert not has_main_guard(module)
    assert isinstance(module.tree.body[1], ast.If)


def test_an_application_built_in_a_test_roots_no_production_world() -> None:
    _, model = _model(
        **{
            "app.py": "from fastapi import FastAPI\n\napp = FastAPI()\n",
            "tests/test_app.py": (
                "from fastapi import FastAPI\n\n"
                "def test_lifespan() -> None:\n"
                "    api = FastAPI()\n"
                "    assert api\n"
            ),
        }
    )

    assert [plan.id.key for plan in model.plans] == ["production:web"]
