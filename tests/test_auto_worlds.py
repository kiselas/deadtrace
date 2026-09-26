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
