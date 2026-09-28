from __future__ import annotations

from pathlib import Path

from deadtrace.analysis import AnalysisResult, analyze
from deadtrace.config import Config
from deadtrace.core import AssemblyState, NodeId, WorldId


def _write(root: Path, path: str, source: str) -> None:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source, encoding="utf-8")


def _node(result: AnalysisResult, target: str) -> NodeId:
    symbol = result.program.resolve_symbol(target)
    assert symbol is not None, target
    return symbol.id


def test_pytest_world_models_fixture_chain_and_test_only_use(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "app.py",
        """
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def live() -> str:
    return "live"

def test_only_helper() -> str:
    return "fixture"

def autouse_helper() -> None:
    pass

def unused() -> None:
    pass
""",
    )
    _write(
        tmp_path,
        "tests/conftest.py",
        """
import pytest
from app import autouse_helper, test_only_helper

@pytest.fixture
def base() -> str:
    return test_only_helper()

@pytest.fixture(name="renamed")
def derived(base: str) -> str:
    return base

@pytest.fixture(autouse=True)
def audit() -> None:
    autouse_helper()
""",
    )
    _write(
        tmp_path,
        "tests/test_app.py",
        """
import pytest

@pytest.mark.usefixtures("audit")
@pytest.mark.parametrize("number, label", [(1, "one")])
def test_endpoint(renamed: str, number: int, label: str, tmp_path) -> None:
    assert renamed and number and label and tmp_path
""",
    )

    result = analyze(tmp_path, Config())
    production = next(world for world in result.snapshot.worlds if world.id.profile != "tests")
    tests = result.snapshot.world(WorldId("tests", "pytest"))

    assert production.assembly_state is AssemblyState.COMPLETE
    assert tests.assembly_state is AssemblyState.COMPLETE
    for target in (
        "tests.test_app:test_endpoint",
        "tests.conftest:base",
        "tests.conftest:derived",
        "tests.conftest:audit",
        "app:test_only_helper",
        "app:autouse_helper",
    ):
        assert tests.state_of(_node(result, target)) is not None, target
    assert production.state_of(_node(result, "app:test_only_helper")) is None
    test_only_names = {
        member.qualified_name
        for finding in result.findings
        if finding.code == "RCH004"
        for member in finding.members
    }
    assert {"test_only_helper", "autouse_helper"} <= test_only_names
    assert any(
        finding.code == "RCH001"
        and any(member.qualified_name == "unused" for member in finding.members)
        for finding in result.findings
    )


def test_unknown_fixture_makes_only_test_world_partial(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "app.py",
        "from fastapi import FastAPI\napp = FastAPI()\n",
    )
    _write(
        tmp_path,
        "test_external.py",
        "def test_external(plugin_fixture) -> None:\n    pass\n",
    )

    result = analyze(tmp_path, Config())
    production = next(world for world in result.snapshot.worlds if world.id.profile != "tests")
    tests = result.snapshot.world(WorldId("tests", "pytest"))

    assert production.assembly_state is AssemblyState.COMPLETE
    assert tests.assembly_state is AssemblyState.PARTIAL
    assert not tests.negative_findings_allowed
    assert "DT3201" in {limitation.code for limitation in tests.limitations}
    assert not result.complete


def test_pytest_plugin_modules_provide_fixtures_to_every_test(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "tests/conftest.py",
        'pytest_plugins = ["tests.fixtures.items", "external_plugin"]\n',
    )
    _write(tmp_path, "tests/fixtures/__init__.py", "")
    _write(
        tmp_path,
        "tests/fixtures/items.py",
        "import pytest\n\n@pytest.fixture\ndef item() -> int:\n    return 1\n",
    )
    _write(tmp_path, "tests/unit/test_sample.py", "def test_sample(item) -> None:\n    pass\n")

    result = analyze(tmp_path, Config())
    tests = result.snapshot.world(WorldId("tests", "pytest"))

    assert tests.assembly_state is AssemblyState.COMPLETE
    assert tests.state_of(_node(result, "tests.fixtures.items:item")) is not None


def test_pytest_plugins_resolve_from_the_directory_above_the_conftest_package(
    tmp_path: Path,
) -> None:
    # pytest puts ``service/`` on sys.path for ``service/service_tests/conftest.py``, whose
    # directory is a package, so ``service_tests.fixtures.battle`` names a namespace portion.
    _write(tmp_path, "service/service_tests/__init__.py", "")
    _write(
        tmp_path,
        "service/service_tests/conftest.py",
        'pytest_plugins = ["service_tests.fixtures.battle"]\n',
    )
    _write(
        tmp_path,
        "service/service_tests/fixtures/battle.py",
        "import pytest\n\n@pytest.fixture\ndef battle() -> int:\n    return 1\n",
    )
    _write(
        tmp_path,
        "service/service_tests/test_battle.py",
        "def test_battle(battle: int) -> None:\n    pass\n",
    )

    result = analyze(tmp_path, Config())
    tests = result.snapshot.world(WorldId("tests", "pytest"))

    assert tests.assembly_state is AssemblyState.COMPLETE
    battle = result.program.modules["service.service_tests.fixtures.battle"]
    fixture = next(symbol for symbol in battle.symbols if symbol.name == "battle")
    assert tests.state_of(fixture.id) is not None


def test_asyncio_fixtures_assigned_patchers_joined_names_and_star_chains(
    tmp_path: Path,
) -> None:
    _write(tmp_path, "proxy.py", "class Proxy:\n    def add_logs(self) -> None:\n        pass\n")
    _write(tmp_path, "tests/__init__.py", "")
    _write(
        tmp_path,
        "tests/conftest.py",
        """
from unittest.mock import patch

import pytest
import pytest_asyncio

from proxy import Proxy

patch_add = patch.object(Proxy, "add_logs")


@pytest_asyncio.fixture
async def revert() -> int:
    return 1


@pytest.fixture
def made(count: int = 3) -> int:
    return 2
""",
    )
    _write(
        tmp_path,
        "tests/test_a.py",
        """
import pytest

from tests.conftest import patch_add


@patch_add
async def test_patched(mock_add, revert: int) -> None:
    pass


@pytest.mark.parametrize(
    "first, second,"
    " third",
    [(1, 2, 3)],
)
def test_params(first, second, third, made) -> None:
    pass
""",
    )
    _write(tmp_path, "tests/arbiter/__init__.py", "")
    _write(tmp_path, "tests/arbiter/conftest.py", "from .fixtures import *  # noqa: F403\n")
    _write(tmp_path, "tests/arbiter/fixtures/__init__.py", "from .workers import *  # noqa: F403\n")
    _write(
        tmp_path,
        "tests/arbiter/fixtures/workers.py",
        "import pytest\n\n@pytest.fixture\ndef worker1() -> int:\n    return 1\n",
    )
    _write(tmp_path, "tests/arbiter/test_w.py", "def test_worker(worker1) -> None:\n    pass\n")

    result = analyze(tmp_path, Config())
    tests = result.snapshot.world(WorldId("tests", "pytest"))

    assert tests.assembly_state is AssemblyState.COMPLETE, tests.limitations
    for fixture in (
        "tests.conftest:revert",
        "tests.conftest:made",
        "tests.arbiter.fixtures.workers:worker1",
    ):
        assert tests.state_of(_node(result, fixture)) is not None


def test_pytest_plugins_serve_the_session_of_the_conftest_naming_them(tmp_path: Path) -> None:
    # Each service of a monorepo is its own pytest session with its own plugin fixtures.
    for service in ("shop", "billing"):
        _write(tmp_path, f"{service}/{service}_tests/__init__.py", "")
        _write(
            tmp_path,
            f"{service}/{service}_tests/conftest.py",
            f'pytest_plugins = ["{service}_tests.fixtures"]\n',
        )
        _write(
            tmp_path,
            f"{service}/{service}_tests/fixtures.py",
            "import pytest\n\n@pytest.fixture\ndef image() -> bytes:\n    return b''\n",
        )
        _write(
            tmp_path,
            f"{service}/{service}_tests/test_images.py",
            "def test_image(image: bytes) -> None:\n    pass\n",
        )

    result = analyze(tmp_path, Config())
    tests = result.snapshot.world(WorldId("tests", "pytest"))

    assert tests.assembly_state is AssemblyState.COMPLETE
    for service in ("shop", "billing"):
        module = result.program.modules[f"{service}.{service}_tests.fixtures"]
        fixture = next(symbol for symbol in module.symbols if symbol.name == "image")
        assert tests.state_of(fixture.id) is not None, service


def test_computed_pytest_plugins_are_reported_as_unknown_collection(tmp_path: Path) -> None:
    _write(tmp_path, "conftest.py", "pytest_plugins = [name for name in PLUGINS]\n")
    _write(tmp_path, "test_sample.py", "def test_sample() -> None:\n    pass\n")

    result = analyze(tmp_path, Config())
    tests = result.snapshot.world(WorldId("tests", "pytest"))

    assert tests.assembly_state is AssemblyState.PARTIAL
    assert any(limitation.code == "DT3202" for limitation in tests.limitations)


def test_pytest_requests_only_the_names_pytest_resolves(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "test_names.py",
        """
from unittest import mock
from unittest.mock import patch

import pytest

pytestmark = [pytest.mark.parametrize("module_value", [1])]

@pytest.fixture
def value() -> int:
    return 1

@pytest.mark.parametrize(("first", "second"), [(1, 2)])
@pytest.mark.parametrize(argnames=["third"], argvalues=[3])
def test_lists_and_keywords(first, second, third, module_value, optional=None) -> None:
    pass

@pytest.mark.parametrize("value", [1], indirect=True)
def test_indirect_names_are_fixtures(value) -> None:
    pass

@patch("os.getcwd")
@mock.patch.object(pytest, "fail")
@patch("os.getpid", new=lambda: 1)
def test_patch_mocks_are_not_fixtures(fail_mock, getcwd_mock, value, *args, **kwargs) -> None:
    pass

@pytest.mark.parametrize("case", [1])
class TestMarkedClass:
    @staticmethod
    def test_static(value, case) -> None:
        pass

    def test_method(self, case, mocker) -> None:
        pass
""",
    )

    result = analyze(tmp_path, Config())
    tests = result.snapshot.world(WorldId("tests", "pytest"))

    assert tests.assembly_state is AssemblyState.COMPLETE, tests.limitations
    assert tests.state_of(_node(result, "test_names:value")) is not None


def test_unresolved_fixtures_do_not_protect_code_in_production_worlds(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "app.py",
        """
import importlib
import sys

def main() -> None:
    importlib.import_module(sys.argv[1])

def unused() -> None:
    pass

if __name__ == "__main__":
    main()
""",
    )
    _write(
        tmp_path,
        "test_app.py",
        "import pytest\n\n@pytest.mark.slow\ndef test_app(unknown_fixture) -> None:\n    pass\n",
    )

    result = analyze(tmp_path, Config())
    scripts = result.snapshot.world(WorldId("production", "scripts"))
    tests = result.snapshot.world(WorldId("tests", "pytest"))

    assert scripts.state_of(_node(result, "app:unused")) is None
    assert tests.state_of(_node(result, "app:unused")) is not None
    assert tests.assembly_state is AssemblyState.PARTIAL


def test_same_module_fixture_and_class_tests_are_collected(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "sample_test.py",
        """
import pytest

@pytest.fixture
def value(request) -> int:
    return 1

class TestGroup:
    def test_method(self, value: int, caplog) -> None:
        assert value

class Helper:
    def test_not_collected(self, missing) -> None:
        pass
""",
    )

    result = analyze(tmp_path, Config())
    tests = result.snapshot.world(WorldId("tests", "pytest"))

    assert tests.assembly_state is AssemblyState.COMPLETE
    assert tests.state_of(_node(result, "sample_test:TestGroup.test_method")) is not None
    assert tests.state_of(_node(result, "sample_test:value")) is not None
    assert tests.state_of(_node(result, "sample_test:Helper.test_not_collected")) is None


def test_fixtures_requested_by_name_at_run_time_are_used(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "conftest.py",
        """
import pytest

@pytest.fixture
def by_lookup() -> int:
    return 1

@pytest.fixture
def lazy_value() -> int:
    return 2

@pytest.fixture
def never_requested() -> int:
    return 3
""",
    )
    _write(
        tmp_path,
        "test_values.py",
        """
import pytest
from pytest_lazy_fixtures import lf

def test_lookup(request) -> None:
    assert request.getfixturevalue("by_lookup")

@pytest.mark.parametrize("value", [lf("lazy_value")])
def test_lazy(value) -> None:
    assert value
""",
    )

    result = analyze(tmp_path, Config())
    tests = result.snapshot.world(WorldId("tests", "pytest"))

    assert tests.assembly_state is AssemblyState.COMPLETE
    assert tests.state_of(_node(result, "conftest:by_lookup")) is not None
    assert tests.state_of(_node(result, "conftest:lazy_value")) is not None
    assert tests.state_of(_node(result, "conftest:never_requested")) is None


def test_a_computed_fixture_lookup_may_request_any_visible_fixture(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "test_values.py",
        """
import pytest

@pytest.fixture
def first() -> int:
    return 1

def test_lookup(request, name: str = "first") -> None:
    assert request.getfixturevalue(name)
""",
    )

    result = analyze(tmp_path, Config())
    tests = result.snapshot.world(WorldId("tests", "pytest"))

    assert tests.state_of(_node(result, "test_values:first")) is not None


def test_fixtures_of_a_pytest11_plugin_are_exported_to_its_users(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "pyproject.toml",
        """
[project]
name = "plugin"
version = "0.0.0"

[project.entry-points.pytest11]
plugin = "plugin_pkg.plugin"
""",
    )
    _write(tmp_path, "plugin_pkg/__init__.py", "")
    _write(
        tmp_path,
        "plugin_pkg/plugin.py",
        """
import pytest

def pytest_configure(config) -> None:
    pass

@pytest.fixture
def exported() -> int:
    return 1

def unused_helper() -> None:
    pass
""",
    )

    result = analyze(tmp_path, Config())
    world = result.snapshot.world(WorldId("production", "entrypoint:pytest11:plugin"))

    assert world.state_of(_node(result, "plugin_pkg.plugin:exported")) is not None
    assert world.state_of(_node(result, "plugin_pkg.plugin:pytest_configure")) is not None
    assert world.state_of(_node(result, "plugin_pkg.plugin:unused_helper")) is None


def test_nested_test_classes_are_collected(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "test_nested.py",
        """
class TestOuter:
    class TestInner:
        def test_inner(self) -> None:
            pass

    class Helper:
        def test_not_collected(self) -> None:
            pass
""",
    )

    result = analyze(tmp_path, Config())
    tests = result.snapshot.world(WorldId("tests", "pytest"))

    assert tests.state_of(_node(result, "test_nested:TestOuter.TestInner.test_inner")) is not None
    assert tests.state_of(_node(result, "test_nested:TestOuter.Helper.test_not_collected")) is None
