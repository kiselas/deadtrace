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
