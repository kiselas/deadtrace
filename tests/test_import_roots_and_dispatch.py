"""Import roots, dynamic modules, and annotation stand-ins (ADR-0015, ADR-0017) stay local.

Each rule adds only what may run: a script's sibling module, the functions a module imported by a
computed name may provide, and the methods of stand-ins that a typed receiver may really be.
Code that merely looks alike stays unreached.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from deadtrace.core import ReachabilityKind, WorldId, WorldPlan, WorldResult, solve
from deadtrace.nominal_types import may_supply_nominal_value
from deadtrace.pytest_semantics import PytestCollection, read_pytest_collection
from deadtrace.python_frontend import (
    PythonProgram,
    build_python_program,
    conftest_directories,
    is_test_path,
)
from deadtrace.receiver_flow import EXTERNAL_RECEIVER, UNKNOWN_RECEIVER, ReceiverValue
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


def test_methods_on_values_from_outside_the_project_may_be_test_stand_ins() -> None:
    program = _program(
        **{
            "client.py": (
                "import requests\n\n"
                "def fetch() -> None:\n"
                "    response = requests.get('x')\n"
                "    response.raise_for_status()\n"
            ),
            "tests/mocks.py": (
                "class FakeResponse:\n"
                "    def raise_for_status(self) -> None:\n"
                "        pass\n\n"
                "    def json(self) -> None:\n"
                "        pass\n"
            ),
            "service.py": (
                "class Response:\n    def raise_for_status(self) -> None:\n        pass\n"
            ),
        }
    )
    world = _world(program, "client:fetch")

    assert _state(program, world, "tests.mocks:FakeResponse.raise_for_status") is not None
    assert _state(program, world, "tests.mocks:FakeResponse.json") is None
    assert _state(program, world, "service:Response.raise_for_status") is None


def test_a_with_target_of_an_outside_manager_is_from_outside() -> None:
    program = _program(
        **{
            "main.py": (
                "def main(path: str) -> None:\n"
                "    with open(path) as stream:\n"
                "        stream.write('x')\n\n"
                "class Store:\n"
                "    def write(self, value: str) -> None:\n"
                "        pass\n"
            ),
        }
    )
    world = _world(program, "main:main")

    assert _state(program, world, "main:Store.write") is None


def test_importing_the_module_of_a_loaded_object_runs_nothing_new() -> None:
    program = _program(
        **{
            "main.py": (
                "import importlib\n\n"
                "def main(value: object) -> None:\n"
                "    importlib.import_module(type(value).__module__)\n"
            ),
            "other.py": "def helper() -> None:\n    pass\n",
        }
    )
    world = _world(program, "main:main")

    assert program.modules["other"].node_id not in world.conservative_may_run


def test_a_package_under_a_source_directory_imports_its_submodules_by_name() -> None:
    program = _program(
        **{
            "backend/app/__init__.py": "",
            "backend/app/main.py": (
                "from app.handlers import build\n\ndef main() -> None:\n    build()\n"
            ),
            "backend/app/handlers/__init__.py": (
                "from app.handlers import poll\n\ndef build() -> None:\n    poll.start()\n"
            ),
            "backend/app/handlers/poll.py": (
                "from app.handlers.shared import helper\n\ndef start() -> None:\n    helper()\n"
            ),
            "backend/app/handlers/shared.py": "def helper() -> None:\n    pass\n",
        }
    )
    world = _world(program, "backend.app.main:main")

    assert _state(program, world, "backend.app.handlers.poll:start") is not None
    assert _state(program, world, "backend.app.handlers.shared:helper") is not None


def test_an_inherited_member_used_through_a_subclass_uses_the_subclass() -> None:
    program = _program(
        **{
            "factories.py": (
                "import factory\n\n"
                "class BaseFactory(factory.Factory):\n"
                "    @classmethod\n"
                "    def build_one(cls) -> object:\n"
                "        return cls._create(dict)\n\n"
                "class ItemFactory(BaseFactory):\n"
                "    @classmethod\n"
                "    def _create(cls, model: type) -> object:\n"
                "        return model()\n\n"
                "class OtherFactory(BaseFactory):\n"
                "    @classmethod\n"
                "    def _create(cls, model: type) -> object:\n"
                "        return model()\n"
            ),
            "main.py": (
                "from factories import ItemFactory\n\n"
                "def run() -> None:\n"
                "    ItemFactory.build_one()\n"
                "    print(ItemFactory.build_one)\n"
            ),
        }
    )
    world = _world(program, "main:run")

    assert _state(program, world, "factories:ItemFactory") is not None
    assert _state(program, world, "factories:ItemFactory._create") is not None
    assert _state(program, world, "factories:OtherFactory") is None


@pytest.mark.parametrize("annotation", ["Path", '"Path"'])
@pytest.mark.parametrize("conditional_import", [False, True])
@pytest.mark.parametrize(
    "body",
    [
        "getattr(value, name)()",
        "alias = value\n    getattr(alias, name)()",
        "callback = getattr(value, name)\n    callback()",
        'callback = getattr(value, "check")\n    callback()',
    ],
)
def test_external_annotation_reflection_protects_members_without_module_wide_guard(
    annotation: str, conditional_import: bool, body: str
) -> None:
    imports = (
        "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from pathlib import Path\n"
        if conditional_import
        else "from pathlib import Path\n"
    )
    program = _program(
        **{
            "main.py": imports
            + "from external import Bridge\n"
            + "class Derived(Path):\n    def check(self): pass\n"
            + "class Indirect(Bridge):\n    def run(self): pass\n"
            + "class Plain:\n    def check(self): pass\n"
            + "def _unused(): pass\n"
            + f"def main(value: {annotation}, name):\n    {body}\n",
            "tests/test_double.py": "class Double:\n    def check(self): pass\n",
        }
    )
    world = _world(program, "main:main")
    for target in ("main:Derived.check", "main:Indirect.run"):
        assert _state(program, world, target) is not None
    assert _state(program, world, "main:Plain.check") is None
    assert _state(program, world, "tests.test_double:Double.check") is not None
    assert _state(program, world, "main:_unused") is None


@pytest.mark.parametrize(
    "imports,annotation,body",
    [
        ("from pathlib import Path", "Path", "value = unknown\n    getattr(value, name)()"),
        (
            "from pathlib import Path",
            "Path",
            "if name:\n        value = unknown\n    getattr(value, name)()",
        ),
        ("from pathlib import Path", "Path", "value = factory()\n    getattr(value, name)()"),
        (
            "from pathlib import Path",
            "Path",
            "alias = value\n    del alias\n    getattr(alias, name)()",
        ),
        (
            "from pathlib import Path",
            "Path",
            "for value in unknown:\n        getattr(value, name)()",
        ),
        (
            "from pathlib import Path",
            "Path",
            "with unknown as value:\n        getattr(value, name)()",
        ),
        ("from pathlib import Path", "Path", "value, other = unknown\n    getattr(value, name)()"),
        (
            "from pathlib import Path",
            "Path",
            "try:\n        value = unknown\n    finally:\n        getattr(value, name)()",
        ),
        ("from pathlib import Path", "Path", "(value := unknown)\n    getattr(value, name)()"),
        ("from typing import Any", "Any", "getattr(value, name)()"),
        ("from typing import Protocol", "Protocol", "getattr(value, name)()"),
        ("from types import ModuleType", "ModuleType", "getattr(value, name)()"),
        ("from pathlib import Path", "list[Path]", "getattr(value, name)()"),
        ("from pathlib import Path", "Path | None", "getattr(value, name)()"),
        ("from pathlib import Path", "unknown", "getattr(value, name)()"),
        (
            "if flag:\n    from pathlib import Path\nelse:\n    from external import Path",
            "Path",
            "getattr(value, name)()",
        ),
    ],
)
def test_external_reflection_unknown_origins_keep_the_whole_graph_guard(
    imports: str, annotation: str, body: str
) -> None:
    program = _program(
        **{
            "main.py": imports
            + "\nfrom external import factory\n"
            + "def _possibly_attached(): pass\n"
            + f"def main(value: {annotation}, name, unknown):\n    {body}\n"
        }
    )
    world = _world(program, "main:main")
    assert _state(program, world, "main:_possibly_attached") is not None


def test_external_reflection_keeps_escaped_function_attributes_protected() -> None:
    program = _program(
        **{
            "main.py": "from pathlib import Path\n"
            "def _attached(): pass\n"
            "def _unused(): pass\n"
            "def main(value: Path, name):\n"
            "    value.callback = _attached\n"
            "    getattr(value, name)()\n"
        }
    )
    world = _world(program, "main:main")
    assert _state(program, world, "main:_attached") is not None
    assert _state(program, world, "main:_unused") is None


def test_external_annotation_provenance_joins_and_forgets_untyped_external_origins() -> None:
    annotated = ReceiverValue(external=True, external_annotation=True)
    assert annotated.join(annotated).external_annotation
    assert annotated.join(ReceiverValue()).external_annotation
    assert not annotated.join(EXTERNAL_RECEIVER).external_annotation
    assert annotated.join(UNKNOWN_RECEIVER).unknown


def test_external_annotation_provenance_survives_destructured_loop_and_return() -> None:
    program = _program(
        **{
            "main.py": "from typing import TYPE_CHECKING\n"
            "if TYPE_CHECKING:\n    from pathlib import Path\n"
            "names = {'check': 'result'}\n"
            "class Derived(Path):\n    def check(self): pass\n"
            "def _unused(): pass\n"
            "def main(p: 'Path') -> str:\n"
            "    assert p.exists(), 'path does not exist'\n"
            "    for method, name in names.items():\n"
            "        if getattr(p, method)():\n"
            "            return name\n"
            "    return 'unknown'\n"
        }
    )
    world = _world(program, "main:main")
    assert _state(program, world, "main:Derived.check") is not None
    assert _state(program, world, "main:_unused") is None


@pytest.mark.parametrize(
    "imports,base",
    [
        ("from logging import LogRecord\nfrom pathlib import Path", "LogRecord"),
        ("from pathlib import Path", "object"),
        ("from pathlib import Path\nimport builtins", "builtins.object"),
        (
            "from pathlib import Path\nfrom typing import Generic, TypeVar\nT = TypeVar('T')",
            "Generic[T]",
        ),
    ],
)
def test_standard_nominal_summary_excludes_unrelated_roots(imports: str, base: str) -> None:
    program = _program(
        **{
            "main.py": imports + f"\nclass Other({base}):\n    def idle(self): pass\n"
            "def main(value: Path, name):\n    getattr(value, name)()\n"
        }
    )
    world = _world(program, "main:main")
    assert _state(program, world, "main:Other.idle") is None


@pytest.mark.parametrize(
    "imports,base",
    [
        ("from pathlib import Path\nfrom external import Bridge", "Bridge"),
        ("from pathlib import Path\nobject = factory()", "object"),
        (
            "from pathlib import Path\nfrom logging import LogRecord\nLogRecord = factory()",
            "LogRecord",
        ),
        (
            "from pathlib import Path\nimport logging\nlogging.LogRecord = factory()",
            "logging.LogRecord",
        ),
        (
            "from pathlib import Path\nif flag:\n    from external import Base\n"
            "else:\n    from logging import LogRecord as Base",
            "Base",
        ),
        ("from pathlib import Path\ndef factory(): pass", "factory()"),
    ],
)
def test_opaque_and_rebound_external_bases_keep_project_members(imports: str, base: str) -> None:
    program = _program(
        **{
            "main.py": imports + f"\nclass Possible({base}):\n    def check(self): pass\n"
            "def main(value: Path, name):\n    getattr(value, name)()\n"
        }
    )
    world = _world(program, "main:main")
    assert _state(program, world, "main:Possible.check") is not None


def test_path_summary_retains_methods_inherited_from_plain_project_mixin() -> None:
    program = _program(
        **{
            "main.py": "from pathlib import Path\n"
            "class Mixin:\n    def check(self): pass\n"
            "class Derived(Mixin, Path): pass\n"
            "def main(value: Path, name):\n    getattr(value, name)()\n"
        }
    )
    world = _world(program, "main:main")
    assert _state(program, world, "main:Mixin.check") is not None


def test_nominal_origins_join_conservatively() -> None:
    path = ReceiverValue(external=True, external_annotation=True, external_nominal="pathlib.Path")
    record = ReceiverValue(
        external=True, external_annotation=True, external_nominal="logging.LogRecord"
    )
    assert path.join(path).external_nominal == "pathlib.Path"
    assert path.join(ReceiverValue()).external_nominal == "pathlib.Path"
    assert ReceiverValue().join(path).external_nominal == "pathlib.Path"
    assert path.join(record).external_nominal is None
    assert path.join(EXTERNAL_RECEIVER).external_nominal is None


@pytest.mark.parametrize(
    "base,possible",
    [
        ("pathlib.PurePosixPath", True),
        ("logging.Handler", False),
        ("unknown.Bridge", True),
        ("builtins.object", False),
    ],
)
def test_standard_nominal_metadata_keeps_unknown_ancestry(base: str, possible: bool) -> None:
    assert may_supply_nominal_value(base, "pathlib.Path") is possible


@pytest.mark.parametrize("expression", ["worker", "Worker()"])
def test_stored_literal_getattr_protects_only_selected_project_method(expression: str) -> None:
    program = _program(
        **{
            "main.py": (
                "class Worker:\n"
                "    def run(self): pass\n"
                "    def idle(self): pass\n"
                "def main():\n"
                "    worker = Worker()\n"
                f"    callback = getattr({expression}, 'run')\n"
                "    callback()\n"
            )
        }
    )
    world = _world(program, "main:main")
    assert _state(program, world, "main:Worker.run") is ReachabilityKind.CONSERVATIVE
    assert _state(program, world, "main:Worker.idle") is None


def test_stored_literal_getattr_includes_inherited_method_and_override() -> None:
    program = _program(
        **{
            "main.py": (
                "class Base:\n"
                "    def run(self): pass\n"
                "    def idle(self): pass\n"
                "class Child(Base):\n"
                "    def run(self): pass\n"
                "def main(worker: Base):\n"
                "    callback = getattr(worker, 'run')\n"
                "    callback()\n"
            )
        }
    )
    world = _world(program, "main:main")
    assert _state(program, world, "main:Base.run") is ReachabilityKind.CONSERVATIVE
    assert _state(program, world, "main:Child.run") is ReachabilityKind.CONSERVATIVE
    assert _state(program, world, "main:Base.idle") is None


def test_stored_literal_getattr_of_project_module() -> None:
    program = _program(
        **{
            "main.py": (
                "import worker\ndef main():\n"
                "    callback = getattr(worker, 'run')\n    callback()\n"
            ),
            "worker.py": "def run(): pass\ndef idle(): pass\n",
        }
    )
    world = _world(program, "main:main")
    assert _state(program, world, "worker:run") is ReachabilityKind.CONSERVATIVE
    assert _state(program, world, "worker:idle") is None


def test_missing_literal_getattr_with_default_does_not_open_graph() -> None:
    program = _program(
        **{
            "main.py": (
                "class Worker:\n    def idle(self): pass\n"
                "def main():\n    worker = Worker()\n"
                "    callback = getattr(worker, 'missing', None)\n"
                "def unused(): pass\n"
            )
        }
    )
    world = _world(program, "main:main")
    assert _state(program, world, "main:Worker.idle") is None
    assert _state(program, world, "main:unused") is None


def test_partial_keyword_override_retains_broad_dispatch_protection() -> None:
    program = _program(
        **{
            "main.py": (
                "from functools import partial\n"
                "class Worker:\n"
                "    def setter(self): pass\n"
                "    def other(self): pass\n"
                "def dispatch(worker, *, name):\n    getattr(worker, name)()\n"
                "def main():\n"
                "    callback = partial(dispatch, Worker(), name='setter')\n"
                "    callback(name='other')\n"
            )
        }
    )
    world = _world(program, "main:main")
    assert _state(program, world, "main:Worker.other") is not None
