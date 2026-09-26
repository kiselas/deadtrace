"""Import roots, dynamic modules, and annotation stand-ins (ADR-0015, ADR-0017) stay local.

Each rule adds only what may run: a script's sibling module, the functions a module imported by a
computed name may provide, and the methods of stand-ins that a typed receiver may really be.
Code that merely looks alike stays unreached.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from deadtrace.core import ReachabilityKind, WorldId, WorldPlan, WorldResult, solve
from deadtrace.pytest_semantics import PytestCollection, read_pytest_collection
from deadtrace.python_frontend import (
    PythonProgram,
    build_python_program,
    conftest_directories,
    is_test_path,
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


def _world(program: PythonProgram, root: str) -> WorldResult:
    world = WorldId("production", "script")
    symbol = program.resolve_symbol(root)
    assert symbol is not None, root
    roots = (symbol.id, program.modules[symbol.module].node_id)
    return solve(program.graph, (WorldPlan(world, roots),)).world(world)


def _state(program: PythonProgram, world: WorldResult, target: str) -> ReachabilityKind | None:
    symbol = program.resolve_symbol(target)
    assert symbol is not None, target
    return world.state_of(symbol.id)


def test_a_script_imports_its_sibling_but_a_package_module_does_not() -> None:
    program = _program(
        **{
            "tools/bench/run.py": "import lab\n\ndef main() -> None:\n    lab.measure()\n",
            "tools/bench/lab.py": (
                "def measure() -> None:\n    pass\n\ndef idle() -> None:\n    pass\n"
            ),
            "pkg/__init__.py": "",
            "pkg/lab.py": "def other() -> None:\n    pass\n",
            "pkg/user.py": "import json\n\ndef main() -> None:\n    json.dumps(1)\n",
            "pkg/json.py": "def dumps(value: object) -> str:\n    return ''\n",
        }
    )

    script = _world(program, "tools.bench.run:main")
    assert _state(program, script, "tools.bench.lab:measure") is ReachabilityKind.RESOLVED
    assert _state(program, script, "tools.bench.lab:idle") is None
    assert _state(program, script, "pkg.lab:other") is None
    packaged = _world(program, "pkg.user:main")
    assert _state(program, packaged, "pkg.json:dumps") is None


def test_a_module_does_not_import_itself_through_its_directory() -> None:
    program = _program(**{"proj/celery.py": "from celery import Celery\n\napp = Celery('x')\n"})

    assert program.modules["proj.celery"].imports["Celery"].target == "celery.Celery"


def test_a_src_directory_is_a_package_only_when_code_imports_it() -> None:
    as_root = _program(**{"src/app/main.py": "", "src/app/__init__.py": ""})
    as_package = _program(
        **{
            "src/__init__.py": "",
            "src/app/__init__.py": "",
            "src/app/main.py": "from src.app import helpers\n",
            "src/app/helpers.py": "",
        }
    )

    assert "app.main" in as_root.modules
    assert "src.app.main" in as_package.modules


def test_attributes_of_a_dynamically_imported_module_are_its_candidates() -> None:
    program = _program(
        **{
            "runner.py": (
                "import importlib\nimport sys\n\n"
                "def main() -> None:\n"
                "    module = importlib.import_module(sys.argv[1])\n"
                "    module.check()\n"
            ),
            "checks/one.py": (
                "def check() -> None:\n    pass\n\ndef unrelated() -> None:\n    pass\n"
            ),
        }
    )
    world = _world(program, "runner:main")

    assert _state(program, world, "checks.one:check") is not None
    assert _state(program, world, "checks.one:unrelated") is None


def test_getattr_on_an_installed_module_protects_no_project_code() -> None:
    program = _program(
        **{
            "main.py": (
                "import operator\n\n"
                "def main(name: str) -> None:\n"
                "    getattr(operator, name)(1, 2)\n\n"
                "def unused() -> None:\n"
                "    pass\n"
            ),
        }
    )
    world = _world(program, "main:main")

    assert _state(program, world, "main:unused") is None


def test_loading_a_module_from_a_path_may_run_any_module() -> None:
    program = _program(
        **{
            "loader.py": (
                "import importlib.util\n\n"
                "def load(path: str) -> None:\n"
                "    spec = importlib.util.spec_from_file_location('plugin', path)\n"
            ),
            "plugins/sample.py": "import sys\n",
        }
    )
    world = _world(program, "loader:load")

    assert program.modules["plugins.sample"].node_id in world.conservative_may_run


def test_typed_calls_reach_protocol_implementations_and_test_stand_ins() -> None:
    program = _program(
        **{
            "service.py": (
                "from typing import Protocol\n\n"
                "class Store(Protocol):\n"
                "    def save(self) -> None: ...\n\n"
                "class Repo:\n"
                "    def load(self) -> None:\n"
                "        pass\n\n"
                "def run(store: Store, repo: Repo) -> None:\n"
                "    store.save()\n"
                "    repo.load()\n"
            ),
            "memory.py": (
                "class MemoryStore:\n"
                "    def save(self) -> None:\n"
                "        pass\n\n"
                "class Unrelated:\n"
                "    def load(self) -> None:\n"
                "        pass\n"
            ),
            "tests/test_service.py": (
                "class FakeRepo:\n    def load(self) -> None:\n        pass\n"
            ),
        }
    )
    world = _world(program, "service:run")

    assert _state(program, world, "memory:MemoryStore.save") is not None
    assert _state(program, world, "tests.test_service:FakeRepo.load") is not None
    assert _state(program, world, "memory:Unrelated.load") is None


def test_enumeration_members_and_nested_options_are_used_through_their_owner() -> None:
    program = _program(
        **{
            "models.py": (
                "from enum import Enum\n"
                "from django.db import models\n\n"
                "class Kind(Enum):\n"
                "    A = 'a'\n\n"
                "class Item(models.Model):\n"
                "    DEFAULT = Kind.A.value\n\n"
                "    class Meta:\n"
                "        ordering = ['id']\n\n"
                "class Plain:\n"
                "    class Meta:\n"
                "        pass\n\n"
                "def main() -> None:\n"
                "    print(Item, Plain)\n"
            ),
        }
    )
    world = _world(program, "models:main")

    assert _state(program, world, "models:Kind") is not None
    assert _state(program, world, "models:Item.Meta") is not None
    assert _state(program, world, "models:Plain.Meta") is None


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("tests/helpers.py", True),
        ("app_tests/api/utils.py", True),
        ("tests_api/client.py", True),
        ("pkg/conftest.py", True),
        ("pkg/test_models.py", True),
        ("pkg/models_test.py", True),
        ("pkg/testimony.py", False),
        ("contest/models.py", False),
    ],
)
def test_test_code_is_recognized_by_pytest_conventions(path: str, expected: bool) -> None:
    assert is_test_path(path) is expected


def test_directories_with_a_conftest_hold_test_code() -> None:
    program = _program(
        **{
            "conftest.py": "",
            "qa/conftest.py": "",
            "qa/helpers.py": "",
            "app/main.py": "",
        }
    )
    trees = conftest_directories(program)

    assert trees == frozenset({"qa"})
    assert is_test_path("qa/helpers.py", trees)
    assert not is_test_path("app/main.py", trees)


@pytest.mark.parametrize(
    ("file_name", "content", "expected"),
    [
        ("pytest.ini", "[pytest]\npython_files = check_*.py\n", ("check_*.py",)),
        (
            "pyproject.toml",
            '[tool.pytest.ini_options]\npython_files = ["a_*.py", "b_*.py"]\n',
            ("a_*.py", "b_*.py"),
        ),
        ("tox.ini", "[pytest]\npython_files = tests.py test_*.py\n", ("tests.py", "test_*.py")),
        ("setup.cfg", "[tool:pytest]\npython_files = t_*.py\n", ("t_*.py",)),
        ("setup.cfg", "[metadata]\nname = x\n", PytestCollection().files),
        ("pyproject.toml", "not = [valid", PytestCollection().files),
    ],
)
def test_pytest_collection_patterns_are_read_from_configuration(
    tmp_path: Path, file_name: str, content: str, expected: tuple[str, ...]
) -> None:
    (tmp_path / file_name).write_text(content, encoding="utf-8")

    assert read_pytest_collection(tmp_path).files == expected
