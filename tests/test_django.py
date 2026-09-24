"""Django installed applications (ADR-0013): what Django loads, and what it leaves alone."""

from __future__ import annotations

from pathlib import Path

from deadtrace.config import Config
from deadtrace.core import EdgeKind, WorldId, WorldPlan, solve
from deadtrace.frameworks import FrameworkModel, build_framework_model
from deadtrace.python_frontend import PythonProgram, build_python_program
from deadtrace.scanner import SourceCollection, SourceUnit


def _model(**sources: str) -> tuple[PythonProgram, FrameworkModel]:
    collection = SourceCollection(
        root=Path("/project"),
        files=tuple(sorted(sources)),
        units=tuple(
            SourceUnit(path, Path("/project") / path, source, f"digest-{path}")
            for path, source in sorted(sources.items())
        ),
        issues=(),
    )
    program = build_python_program(collection)
    return program, build_framework_model(program, Config())


def _imported(program: PythonProgram, model: FrameworkModel, settings: str) -> set[str]:
    source = program.modules[settings].node_id
    names = {module.node_id: name for name, module in program.modules.items()}
    return {
        names[edge.target]
        for edge in model.graph.edges
        if edge.source == source and edge.detail.startswith("Django imports")
    }


def test_each_settings_module_roots_its_own_world() -> None:
    _, model = _model(
        **{
            "site/__init__.py": "",
            "site/settings/__init__.py": "",
            "site/settings/base.py": 'INSTALLED_APPS = ["shop"]\n',
            "site/settings/prod.py": (
                'from site.settings.base import *\n\nINSTALLED_APPS += ["billing"]\n'
            ),
            "shop/__init__.py": "",
            "billing/__init__.py": "",
        }
    )

    assert sorted(plan.id.key for plan in model.plans) == [
        "production:django:site.settings.base",
        "production:django:site.settings.prod",
    ]


def test_installed_apps_come_from_app_lists_and_app_configs() -> None:
    program, model = _model(
        **{
            "conf.py": (
                'LOCAL_APPS = ["orders.config.OrdersConfig"]\n'
                'INSTALLED_APPS = ["django.contrib.admin", "catalog", *LOCAL_APPS]\n'
            ),
            "catalog/__init__.py": "",
            "catalog/models.py": "class Item:\n    pass\n",
            "catalog/views.py": "def index():\n    pass\n",
            "orders/__init__.py": "",
            "orders/config.py": (
                "from django.apps import AppConfig\n\n"
                "class OrdersConfig(AppConfig):\n"
                '    name = "orders.core"\n'
            ),
            "orders/core/__init__.py": "",
            "orders/core/admin.py": "",
            "orders/core/templatetags/__init__.py": "",
            "orders/core/templatetags/money.py": "",
            "orders/models.py": "",
        }
    )

    assert _imported(program, model, "conf") == {
        "catalog",
        "catalog.models",
        "orders.core",
        "orders.core.admin",
        "orders.core.templatetags.money",
    }
    item = program.resolve_symbol("catalog.models:Item")
    assert item is not None
    assert any(
        edge.target == item.id and edge.kind is EdgeKind.CONSTRUCT for edge in model.graph.edges
    )


def test_app_lists_alone_are_not_settings() -> None:
    _, model = _model(**{"lists.py": 'LOCAL_APPS = ["shop"]\n', "shop/__init__.py": ""})

    assert all(not plan.id.scenario.startswith("django") for plan in model.plans)


def test_only_command_modules_with_a_command_class_are_instantiated() -> None:
    program, model = _model(
        **{
            "settings.py": 'INSTALLED_APPS = ["tools"]\n',
            "tools/__init__.py": "",
            "tools/management/__init__.py": "",
            "tools/management/commands/__init__.py": "",
            "tools/management/commands/sync.py": (
                "from django.core.management.base import BaseCommand\n\n"
                "class Command(BaseCommand):\n"
                "    def handle(self, *args, **options):\n"
                "        pass\n"
            ),
            "tools/management/commands/_helpers.py": "def helper():\n    pass\n",
        }
    )
    constructed = {
        str(edge.target)
        for edge in model.graph.edges
        if edge.detail.startswith("Django instantiates")
    }

    assert constructed == {"py:tools.management.commands.sync:Command:class:0"}
    helper = program.resolve_symbol("tools.management.commands._helpers:helper")
    world = WorldId("production", "settings")
    result = solve(model.graph, (WorldPlan(world, (program.modules["settings"].node_id,)),)).world(
        world
    )
    assert helper is not None and result.state_of(helper.id) is None
    assert program.modules["tools.management.commands._helpers"].node_id not in (
        result.resolved_may_run | result.conservative_may_run
    )


def test_strings_name_a_module_attribute_only_when_the_module_binds_it() -> None:
    program, model = _model(
        **{
            "settings.py": (
                "INSTALLED_APPS = []\n"
                'WSGI_APPLICATION = "site_wsgi.application"\n'
                'OTHER = "lonely.missing"\n'
            ),
            "site_wsgi.py": "def configure():\n    pass\n\nconfigure()\napplication = object()\n",
            "lonely.py": "def configure():\n    pass\n\nconfigure()\n",
        }
    )
    world = WorldId("production", "settings")
    result = solve(model.graph, (WorldPlan(world, (program.modules["settings"].node_id,)),)).world(
        world
    )
    reached = program.resolve_symbol("site_wsgi:configure")
    unreached = program.resolve_symbol("lonely:configure")

    assert reached is not None and result.state_of(reached.id) is not None
    assert unreached is not None and result.state_of(unreached.id) is None
