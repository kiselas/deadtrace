"""Static pytest collection and fixture semantics for an isolated tests world."""

from __future__ import annotations

import ast
import configparser
import shlex
import tomllib
from collections.abc import Collection
from dataclasses import dataclass, replace
from fnmatch import fnmatchcase
from pathlib import Path, PurePosixPath

from deadtrace.artifacts import MAX_ARTIFACT_BYTES, InputTooLargeError, read_bounded_bytes
from deadtrace.config import Config
from deadtrace.core import (
    AssemblyState,
    EdgeKind,
    ExecutionEdge,
    Limitation,
    NodeId,
    NodeKind,
    Requirement,
    SemanticGraph,
    UnknownBoundary,
    WorldId,
    WorldPlan,
)
from deadtrace.frameworks import FrameworkModel
from deadtrace.python_frontend import (
    PythonModule,
    PythonProgram,
    PythonSymbol,
    _dotted_name,
    call_arguments,
    follow_module_alias,
    is_fixture_decorator,
    is_function,
    keyword_argument,
)

_BUILTIN_FIXTURES = frozenset(
    {
        "cache",
        "capfd",
        "capfdbinary",
        "caplog",
        "capsys",
        "capsysbinary",
        "doctest_namespace",
        "monkeypatch",
        "pytestconfig",
        "record_property",
        "record_testsuite_property",
        "record_xml_attribute",
        "recwarn",
        "request",
        "tmp_path",
        "tmp_path_factory",
        "tmpdir",
        "tmpdir_factory",
        "pytester",
        "testdir",
        "subtests",
        "capteesys",
    }
)
_PLUGIN_FIXTURES = frozenset(
    {
        # pytest-mock
        "mocker",
        "class_mocker",
        "module_mocker",
        "package_mocker",
        "session_mocker",
        # pytest-asyncio and anyio
        "event_loop",
        "event_loop_policy",
        "unused_tcp_port",
        "unused_tcp_port_factory",
        "unused_udp_port",
        "unused_udp_port_factory",
        "anyio_backend",
        "anyio_backend_name",
        "anyio_backend_options",
        "free_tcp_port",
        "free_tcp_port_factory",
        "free_udp_port",
        "free_udp_port_factory",
        # pytest-django
        "admin_client",
        "admin_user",
        "async_client",
        "async_rf",
        "client",
        "db",
        "django_assert_max_num_queries",
        "django_assert_num_queries",
        "django_capture_on_commit_callbacks",
        "django_db_blocker",
        "django_db_setup",
        "django_user_model",
        "django_username_field",
        "live_server",
        "mailoutbox",
        "rf",
        "settings",
        "transactional_db",
        # HTTP mocking, time, data, and snapshot plugins
        "aioresponses",
        "benchmark",
        "faker",
        "freezer",
        "httpserver",
        "httpx_mock",
        "requests_mock",
        "respx_mock",
        "snapshot",
        "time_machine",
        # Celery's pytest plugin and pytest-celery
        "celery_app",
        "celery_config",
        "celery_enable_logging",
        "celery_includes",
        "celery_parameters",
        "celery_session_app",
        "celery_session_worker",
        "celery_setup",
        "celery_worker",
        "celery_worker_parameters",
        "celery_worker_pool",
        "use_celery_app_trap",
        # pytest-xdist
        "testrun_uid",
        "worker_id",
        # pytest-playwright and pytest-base-url
        "base_url",
        "browser",
        "browser_channel",
        "browser_context_args",
        "browser_name",
        "browser_type",
        "browser_type_launch_args",
        "context",
        "device",
        "is_chromium",
        "is_firefox",
        "is_webkit",
        "launch_browser",
        "new_context",
        "output_path",
        "page",
        "playwright",
        # pytest-click
        "cli_runner",
        "isolated_cli_runner",
        # pytest-aiohttp
        "aiohttp_client",
        "aiohttp_raw_server",
        "aiohttp_server",
        "aiohttp_unused_port",
    }
)
"""Fixtures of widely used third-party plugins (ADR-0016). A test that requests one does not
run project code through it, so it is not an unknown boundary; a project fixture of the same
name is found first and wins."""


@dataclass(frozen=True, slots=True)
class Fixture:
    name: str
    symbol: NodeId
    module: str
    path: str
    autouse: bool
    dependencies: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PytestCollection:
    """The ``python_files``, ``python_classes``, and ``python_functions`` pytest collects by."""

    files: tuple[str, ...] = ("test_*.py", "*_test.py")
    classes: tuple[str, ...] = ("Test",)
    functions: tuple[str, ...] = ("test",)
    plugins: tuple[str, ...] = ()
    """Modules that ``addopts`` loads with ``-p``."""


def read_pytest_collection(root: Path) -> PytestCollection:
    """Read collection patterns from the first pytest configuration file at ``root``.

    pytest uses the first of ``pytest.ini``, ``pyproject.toml`` with
    ``[tool.pytest.ini_options]``, ``tox.ini`` with ``[pytest]``, and ``setup.cfg`` with
    ``[tool:pytest]``. Files are read as data; an unreadable one leaves pytest's defaults.
    """

    sections: list[tuple[str, str]] = [
        ("pytest.ini", "pytest"),
        ("pyproject.toml", ""),
        ("tox.ini", "pytest"),
        ("setup.cfg", "tool:pytest"),
    ]
    for file_name, section in sections:
        path = root / file_name
        if not path.is_file():
            continue
        values = _pytest_options(path, section)
        if values is None:
            continue
        default = PytestCollection()
        return PytestCollection(
            files=values.get("python_files", default.files),
            classes=values.get("python_classes", default.classes),
            functions=values.get("python_functions", default.functions),
            plugins=values.get("plugins", default.plugins),
        )
    return PytestCollection()


def _pytest_options(path: Path, section: str) -> dict[str, tuple[str, ...]] | None:
    """Collection options of one configuration file, or ``None`` if it configures no pytest."""

    options: dict[str, tuple[str, ...]] = {}
    names = ("python_files", "python_classes", "python_functions")
    try:
        source = read_bounded_bytes(path, limit=MAX_ARTIFACT_BYTES).decode("utf-8")
        if not section:
            document = tomllib.loads(source)
            tool = document.get("tool", {})
            if not isinstance(tool, dict):
                return None
            table = tool.get("pytest", {})
            table = table.get("ini_options", table) if isinstance(table, dict) else None
            if not isinstance(table, dict):
                return None
            for name in names:
                value = table.get(name)
                if isinstance(value, str):
                    options[name] = tuple(value.split())
                elif isinstance(value, list) and all(isinstance(item, str) for item in value):
                    options[name] = tuple(value)
            _add_plugins(options, table.get("addopts"))
            return options
        parser = configparser.ConfigParser(interpolation=None)
        parser.read_string(source, source=str(path))
    except (
        OSError,
        UnicodeError,
        InputTooLargeError,
        RecursionError,
        tomllib.TOMLDecodeError,
        configparser.Error,
    ):
        return None
    if not parser.has_section(section):
        return None
    for name in names:
        if parser.has_option(section, name):
            options[name] = tuple(parser.get(section, name).split())
    if parser.has_option(section, "addopts"):
        _add_plugins(options, parser.get(section, "addopts"))
    return options


def _add_plugins(options: dict[str, tuple[str, ...]], addopts: object) -> None:
    """Modules named by ``-p`` in ``addopts``; ``-p no:name`` disables a plugin instead."""

    if isinstance(addopts, str):
        try:
            words = shlex.split(addopts)
        except ValueError:
            return
    elif isinstance(addopts, list) and all(isinstance(item, str) for item in addopts):
        words = list(addopts)
    else:
        return
    found: list[str] = []
    for index, word in enumerate(words):
        if word == "-p" and index + 1 < len(words):
            name = words[index + 1]
        elif word.startswith("-p") and len(word) > 2 and not word.startswith("--"):
            name = word[2:]
        else:
            continue
        if not name.startswith("no:"):
            found.append(name)
    if found:
        options["plugins"] = tuple(found)


def apply_pytest_model(
    program: PythonProgram,
    model: FrameworkModel,
    config: Config,
    *,
    plugin_modules: tuple[str, ...] = (),
    collection: PytestCollection | None = None,
) -> FrameworkModel:
    """Add one isolated pytest world when statically collectable tests exist.

    Fixture resolution and unresolved fixtures are facts of the tests world only (ADR-0016): the
    edges and boundaries they produce live in its plan, not in the shared graph, so that a
    production world that reaches a test conservatively does not inherit them. ``plugin_modules``
    names project modules registered as ``pytest11`` plugins, whose fixtures every test sees.
    ``collection`` gives the configured test file, class, and function patterns.
    """

    del config
    collection = collection if collection is not None else PytestCollection()
    collection = _with_unittest_modules(program, collection)
    plugin_modules = (*plugin_modules, *collection.plugins)
    imported_functions, imported_classes = _imported_tests(program, collection)
    classes = _collected_classes(program, collection, set(imported_classes))
    native = {
        symbol.id
        for symbol in program.symbols.values()
        if _is_test_symbol(program, symbol, collection, classes)
    }
    # A class imported into a test module is collected there, with the methods of its project
    # bases; its tests resolve their fixtures from the importer's directory and namespace.
    importers: dict[NodeId, list[PythonModule]] = {
        key: list(value) for key, value in imported_functions.items()
    }
    for class_id, modules in imported_classes.items():
        for item in _project_ancestry(program, program.symbols[class_id]):
            importers.setdefault(item.id, []).extend(modules)
    tests = tuple(
        symbol
        for symbol in program.symbols.values()
        if symbol.id in native or symbol.id in imported_functions
    )
    # pytest imports every module that matches ``python_files``, tests or not: tests that a module
    # creates dynamically, such as ``TestDraft = suite.to_unittest_testcase()``, need it to run.
    test_modules = tuple(
        module for module in program.modules.values() if _is_test_path(module.path, collection)
    )
    if not tests and not test_modules:
        return model

    fixtures = _discover_fixtures(program)
    requirements = list(model.graph.requirements)
    edges: list[ExecutionEdge] = []
    boundaries: list[UnknownBoundary] = []
    roots: set[NodeId] = set()
    limitations: list[Limitation] = []
    world = WorldId("tests", "pytest")
    all_nodes = tuple(node.id for node in model.graph.nodes)
    plugins, scoped_plugins, plugin_limitations = _pytest_plugins(program, world, plugin_modules)
    # Installed plugins serve every test; ``pytest_plugins`` those of the session whose root
    # conftest names them, as each service of a monorepo is tested apart (ADR-0022).
    installed = {name for name in plugin_modules if name in program.modules}
    global_fixtures = {fixture.name: fixture for fixture in fixtures if fixture.module in installed}
    scopes = _FixtureScopes(program, fixtures, scoped_plugins)
    plugin_fallback: dict[str, list[Fixture]] = {}
    for fixture in fixtures:
        if fixture.module in plugins and fixture.module not in installed:
            plugin_fallback.setdefault(fixture.name, []).append(fixture)
    by_name: dict[str, list[Fixture]] = {}
    for fixture in fixtures:
        by_name.setdefault(fixture.name, []).append(fixture)
    roots.update(_hook_implementations(program, plugins))
    roots.update(classes)
    # pytest imports every conftest and plugin module, which runs their top-level code.
    roots.update(
        module.node_id
        for name, module in program.modules.items()
        if name in plugins or PurePosixPath(module.path).name == "conftest.py"
    )
    roots.update(module.node_id for module in test_modules)
    roots.update(_xunit_fixtures(program, collection, classes))
    # Plugins request the fixtures they define themselves, and a project fixture of such a name
    # overrides theirs: pytest-asyncio's ``event_loop``, pytest-django's ``django_db_setup``.
    roots.update(fixture.symbol for fixture in fixtures if fixture.name in _PLUGIN_FIXTURES)

    # A parametrize mark may also give a value to an argument of a fixture the test requests,
    # which then runs no fixture code for it.
    parametrized_anywhere = {
        name
        for test in tests
        for name in _parameterized_names(program, program.modules[test.module], test)
    }
    for test in tests:
        module = program.modules[test.module]
        roots.add(test.id)
        roots.add(module.node_id)
        contexts = [(test.path, test.module)] if test.id in native else []
        for importer in importers.get(test.owner if test.owner is not None else test.id, ()):
            roots.add(importer.node_id)
            contexts.append((importer.path, importer.name))
        for context_path, context_module in contexts:
            visible = _visible_fixtures(context_path, context_module, scopes, global_fixtures)
            parameterized = _parameterized_names(program, module, test)
            generated = scopes.generates_tests(context_path, context_module)
            requested = {
                name
                for name in _requested_argument_names(program, module, test)
                if name not in parameterized and not (generated and name not in visible)
            }
            requested.update(_usefixtures_names(program, module, test))
            requested.update(fixture.name for fixture in visible.values() if fixture.autouse)
            requested.update(_fixture_values(module, test, visible))
            requested.update(_lazy_fixtures(program, module, test))
            _connect_fixture_requests(
                source=test.id,
                requested=requested,
                visible=visible,
                edges=edges,
                boundaries=boundaries,
                limitations=limitations,
                world=world,
                all_nodes=all_nodes,
                fallback=plugin_fallback,
            )

    fixture_limitations: dict[NodeId, list[Limitation]] = {}
    for fixture in fixtures:
        visible = _visible_fixtures(fixture.path, fixture.module, scopes, global_fixtures)
        generated = scopes.generates_tests(fixture.path, fixture.module)
        _connect_fixture_requests(
            source=fixture.symbol,
            requested={
                *(
                    name
                    for name in fixture.dependencies
                    if name in visible or not (name in parametrized_anywhere or generated)
                ),
                *_fixture_values(
                    program.modules[fixture.module], program.symbols[fixture.symbol], visible
                ),
            },
            visible=visible,
            edges=edges,
            boundaries=boundaries,
            limitations=fixture_limitations.setdefault(fixture.symbol, []),
            world=world,
            all_nodes=all_nodes,
            fallback=plugin_fallback,
        )
        # pytest resolves a fixture's arguments from the test that requests it, so a fixture
        # of that name overriding the visible one closer to a test may run instead.
        directory = PurePosixPath(fixture.path).parent
        for name in fixture.dependencies:
            chosen = visible.get(name)
            edges.extend(
                ExecutionEdge(
                    fixture.symbol,
                    item.symbol,
                    EdgeKind.DEPENDENCY,
                    f"a test below may resolve fixture {name} to an override",
                )
                for item in by_name.get(name, ())
                if (chosen is None or item.symbol != chosen.symbol)
                and _is_parent(directory, PurePosixPath(item.path).parent)
            )
    # A fixture no test can request never runs, so an argument it cannot resolve limits nothing.
    requested_fixtures = _reachable(roots, edges)
    for symbol, found in fixture_limitations.items():
        if symbol in requested_fixtures:
            limitations.extend(found)

    limitations.extend(plugin_limitations)
    assembly = AssemblyState.PARTIAL if limitations else AssemblyState.COMPLETE
    test_plan = WorldPlan(
        id=world,
        roots=tuple(sorted(roots)),
        assembly_state=assembly,
        limitations=tuple(sorted(set(limitations), key=_limitation_sort_key)),
        edges=tuple(sorted(set(edges), key=_edge_sort_key)),
        boundaries=tuple(sorted(set(boundaries), key=_boundary_sort_key)),
    )
    plans = (*(plan for plan in model.plans if plan.id != world), test_plan)
    graph = SemanticGraph(
        nodes=model.graph.nodes,
        edges=model.graph.edges,
        requirements=tuple(sorted(set(requirements), key=_requirement_sort_key)),
        boundaries=model.graph.boundaries,
    )
    return replace(
        model,
        graph=graph,
        plans=tuple(sorted(plans, key=lambda item: item.id)),
    )


def _discover_fixtures(program: PythonProgram) -> tuple[Fixture, ...]:
    fixtures: list[Fixture] = []
    for symbol in program.symbols.values():
        if not is_function(symbol):
            continue
        module = program.modules[symbol.module]
        for expression in symbol.decorators:
            function = expression.func if isinstance(expression, ast.Call) else expression
            if not is_fixture_decorator(_expanded_name(module, function)):
                continue
            fixture_name = symbol.name
            autouse = False
            if isinstance(expression, ast.Call):
                name_value = _string_value(_keyword(expression, "name"))
                if name_value is not None:
                    fixture_name = name_value
                autouse_value = _keyword(expression, "autouse")
                autouse = _dotted_name(autouse_value) == "True"
            # pytest requests a fixture's arguments as a test's: none with a default value.
            dependencies = tuple(
                name
                for name in _requested_argument_names(program, module, symbol)
                if name not in {"self", "cls", "request"}
            )
            fixtures.append(
                Fixture(
                    name=fixture_name,
                    symbol=symbol.id,
                    module=symbol.module,
                    path=symbol.path,
                    autouse=autouse,
                    dependencies=dependencies,
                )
            )
            break
    return tuple(sorted(fixtures, key=lambda item: (item.path, item.name, str(item.symbol))))


class _FixtureScopes:
    """The fixtures of each module's namespace, and the conftest modules by directory.

    pytest registers the fixture functions a module's namespace holds, so a fixture imported into
    a test module or a conftest, by name or with ``*``, is visible there as if defined in it.
    """

    def __init__(
        self,
        program: PythonProgram,
        fixtures: tuple[Fixture, ...],
        scoped_plugins: dict[PurePosixPath, set[str]] | None = None,
    ) -> None:
        by_symbol = {fixture.symbol: fixture for fixture in fixtures}
        self.plugin_scopes: list[tuple[PurePosixPath, dict[str, Fixture]]] = sorted(
            (
                (
                    directory,
                    {
                        fixture.name: fixture
                        for fixture in fixtures
                        if fixture.module in sorted(modules)
                    },
                )
                for directory, modules in (scoped_plugins or {}).items()
            ),
            key=lambda item: (len(item[0].parts), str(item[0])),
        )
        defined: dict[str, dict[str, Fixture]] = {}
        for fixture in fixtures:
            defined.setdefault(fixture.module, {})[fixture.name] = fixture
        self.namespaces: dict[str, dict[str, Fixture]] = {}
        self.conftests: list[tuple[PurePosixPath, str]] = []
        resolving: set[str] = set()

        def namespace_of(name: str) -> dict[str, Fixture]:
            # ``from .fixtures import *`` also brings what ``fixtures`` itself star-imports.
            if name in self.namespaces or name in resolving or name not in program.modules:
                return self.namespaces.get(name, {})
            resolving.add(name)
            module = program.modules[name]
            namespace: dict[str, Fixture] = {}
            for base in module.star_imports:
                namespace.update(
                    (fixture_name, fixture)
                    for fixture_name, fixture in namespace_of(base).items()
                    if not fixture_name.startswith("_")
                )
            for local, binding in module.imports.items():
                target = program.resolve_symbol(binding.target)
                imported = by_symbol.get(target.id) if target is not None else None
                if target is not None and imported is not None:
                    namespace[imported.name if local == target.name else local] = imported
            namespace.update(defined.get(name, {}))
            resolving.discard(name)
            if namespace:
                self.namespaces[name] = namespace
            return namespace

        for name, module in program.modules.items():
            namespace_of(name)
            path = PurePosixPath(module.path)
            if path.name == "conftest.py":
                self.conftests.append((path.parent, name))
        self.conftests.sort(key=lambda item: len(item[0].parts))
        self._directory_cache: dict[str, dict[str, Fixture]] = {}
        self.generators = {
            name
            for name, module in program.modules.items()
            if any(
                symbol.owner is None and symbol.name == "pytest_generate_tests"
                for symbol in module.symbols
            )
        }

    def directory_fixtures(
        self, directory: str, global_fixtures: dict[str, Fixture]
    ) -> dict[str, Fixture]:
        """Plugin fixtures and those of the conftests at or above ``directory``, outside in."""

        cached = self._directory_cache.get(directory)
        if cached is not None:
            return cached
        visible: dict[str, Fixture] = dict(global_fixtures)
        for plugin_directory, plugin_fixtures in self.plugin_scopes:
            if _is_parent(plugin_directory, PurePosixPath(directory)):
                visible.update(plugin_fixtures)
        for conftest_directory, module in self.conftests:
            if _is_parent(conftest_directory, PurePosixPath(directory)):
                visible.update(self.namespaces.get(module, {}))
        self._directory_cache[directory] = visible
        return visible

    def generates_tests(self, consumer_path: str, consumer_module: str) -> bool:
        """Whether a ``pytest_generate_tests`` hook may parametrize the consumer's arguments.

        Such a hook in the consumer's module or a conftest above it may give any argument a value
        at collection time; an argument no fixture provides is then taken to be one of those.
        """

        if consumer_module in self.generators:
            return True
        parent = PurePosixPath(consumer_path).parent
        return any(
            module in self.generators and _is_parent(directory, parent)
            for directory, module in self.conftests
        )


def _visible_fixtures(
    consumer_path: str,
    consumer_module: str,
    scopes: _FixtureScopes,
    global_fixtures: dict[str, Fixture],
) -> dict[str, Fixture]:
    """Fixtures a consumer sees: plugins', then conftests' from the outside in, then its own."""

    visible = dict(scopes.directory_fixtures(consumer_path.rpartition("/")[0], global_fixtures))
    visible.update(scopes.namespaces.get(consumer_module, {}))
    return visible


def _connect_fixture_requests(
    *,
    source: NodeId,
    requested: set[str],
    visible: dict[str, Fixture],
    edges: list[ExecutionEdge],
    boundaries: list[UnknownBoundary],
    limitations: list[Limitation],
    world: WorldId,
    all_nodes: tuple[NodeId, ...],
    fallback: dict[str, list[Fixture]] | None = None,
) -> None:
    for name in sorted(requested):
        fixture = visible.get(name)
        if fixture is not None:
            edges.append(
                ExecutionEdge(
                    source,
                    fixture.symbol,
                    EdgeKind.DEPENDENCY,
                    f"pytest resolves fixture {name}",
                )
            )
        elif fallback and name in fallback:
            # A plugin named by another conftest serves this test too when one pytest session
            # collects both directories.
            edges.extend(
                ExecutionEdge(
                    source,
                    item.symbol,
                    EdgeKind.DEPENDENCY,
                    f"a pytest plugin of another directory may provide fixture {name}",
                )
                for item in fallback[name]
            )
        elif name not in _BUILTIN_FIXTURES and name not in _PLUGIN_FIXTURES:
            limitations.append(
                Limitation(
                    code="DT3201",
                    message=f"pytest fixture or parametrization cannot be resolved: {name}",
                    origin=source,
                    world=world,
                )
            )
            boundaries.append(
                UnknownBoundary(
                    source=source,
                    domain="pytest_fixture_resolution",
                    reason=f"unresolved pytest fixture {name}",
                    targets=all_nodes,
                )
            )


def _is_test_symbol(
    program: PythonProgram,
    symbol: PythonSymbol,
    collection: PytestCollection,
    classes: dict[NodeId, bool],
) -> bool:
    """A test function or method as pytest collects it with the configured name patterns.

    A function counts in a test module. A method counts in a class that ``classes`` collects,
    whether that class is itself a test class or a project base class a test class inherits it
    from; in ``unittest.TestCase`` hierarchies method names only need to start with ``test``.
    """

    if not is_function(symbol):
        return False
    if symbol.owner is None:
        return _is_test_path(symbol.path, collection) and _matches(
            symbol.name, collection.functions
        )
    unittest_case = classes.get(symbol.owner)
    if unittest_case is None:
        return False
    if unittest_case:
        return symbol.name.startswith("test")
    return _matches(symbol.name, collection.functions)


XUNIT_METHODS = frozenset(
    {
        "setup_method",
        "teardown_method",
        "setup_class",
        "teardown_class",
        "setUp",
        "tearDown",
        "setUpClass",
        "tearDownClass",
        "asyncSetUp",
        "asyncTearDown",
    }
)
XUNIT_FUNCTIONS = frozenset(
    {
        "setup_module",
        "teardown_module",
        "setup_function",
        "teardown_function",
        "setUpModule",
        "tearDownModule",
    }
)


def _xunit_fixtures(
    program: PythonProgram, collection: PytestCollection, classes: dict[NodeId, bool]
) -> set[NodeId]:
    """Setup and teardown methods of collected classes and functions of test modules."""

    return {
        symbol.id
        for symbol in program.symbols.values()
        if is_function(symbol)
        and (
            (symbol.owner in classes and symbol.name in XUNIT_METHODS)
            or (
                symbol.owner is None
                and symbol.name in XUNIT_FUNCTIONS
                and _is_test_path(symbol.path, collection)
            )
        )
    }


def _collected_classes(
    program: PythonProgram, collection: PytestCollection, imported: Collection[NodeId] = ()
) -> dict[NodeId, bool]:
    """Classes whose methods pytest collects, and whether each is in a ``unittest`` hierarchy.

    pytest collects top-level classes of test modules that match ``python_classes`` or subclass
    ``unittest.TestCase``, with every method they define or inherit, so the project base classes
    of such a class are collected too, wherever they are defined. ``imported`` are classes that a
    test module imports, which it collects as well.
    """

    collected: dict[NodeId, bool] = {}
    classes = sorted(
        (symbol for symbol in program.symbols.values() if symbol.kind is NodeKind.CLASS),
        key=lambda item: item.qualified_name.count("."),
    )
    for symbol in classes:
        # pytest also collects a matching class nested in a collected one.
        if (symbol.owner is not None and symbol.owner not in collected) or not (
            _is_test_path(symbol.path, collection) or symbol.id in imported
        ):
            continue
        ancestry = _project_ancestry(program, symbol)
        unittest_case = any(_is_unittest_case(program, item) for item in ancestry)
        if not unittest_case and not _matches(symbol.name, collection.classes):
            continue
        for item in ancestry:
            collected[item.id] = collected.get(item.id, False) or unittest_case
    return collected


def _imported_tests(
    program: PythonProgram, collection: PytestCollection
) -> tuple[dict[NodeId, list[PythonModule]], dict[NodeId, list[PythonModule]]]:
    """Test functions and classes that test modules import from other modules.

    pytest collects the functions and classes a module's namespace binds, wherever they are
    defined, so ``from suite import *`` in a test module repeats the suite there, against the
    fixtures and conftests of that module's directory.
    """

    functions: dict[NodeId, list[PythonModule]] = {}
    classes: dict[NodeId, list[PythonModule]] = {}
    public: dict[str, dict[str, PythonSymbol]] = {}

    def bound(name: str, active: frozenset[str]) -> dict[str, PythonSymbol]:
        """Public project definitions a ``from name import *`` binds."""

        if name in public:
            return public[name]
        module = program.modules.get(name)
        if module is None or name in active:
            return {}
        names: dict[str, PythonSymbol] = {}
        for base in module.star_imports:
            names.update(bound(base, active | {name}))
        names.update(_import_bindings(program, module))
        names.update((symbol.name, symbol) for symbol in module.symbols if symbol.owner is None)
        result = {key: value for key, value in names.items() if not key.startswith("_")}
        public[name] = result
        return result

    for name, module in program.modules.items():
        if not _is_test_path(module.path, collection):
            continue
        names = {}
        for base in module.star_imports:
            names.update(bound(base, frozenset({name})))
        names.update(_import_bindings(program, module))
        for local, symbol in names.items():
            if symbol.module == name or symbol.owner is not None:
                continue
            if is_function(symbol) and _matches(local, collection.functions):
                functions.setdefault(symbol.id, []).append(module)
            elif symbol.kind is NodeKind.CLASS and (
                _matches(local, collection.classes)
                or any(
                    _is_unittest_case(program, item) for item in _project_ancestry(program, symbol)
                )
            ):
                classes.setdefault(symbol.id, []).append(module)
    return functions, classes


def _import_bindings(program: PythonProgram, module: PythonModule) -> dict[str, PythonSymbol]:
    """Project definitions a module imports by name, under the names it binds them to."""

    found: dict[str, PythonSymbol] = {}
    for local, binding in module.imports.items():
        target = program.resolve_symbol(binding.target)
        if target is not None:
            found[local] = target
    return found


def _project_ancestry(program: PythonProgram, class_symbol: PythonSymbol) -> list[PythonSymbol]:
    """A class and the project classes it derives from, each once."""

    found: dict[NodeId, PythonSymbol] = {}
    stack = [class_symbol]
    while stack:
        current = stack.pop()
        if current.id in found:
            continue
        found[current.id] = current
        module = program.modules[current.module]
        for base in current.bases:
            name = _expanded_name(module, base)
            target = program.resolve_symbol(name) if name else None
            if target is not None and target.kind is NodeKind.CLASS:
                stack.append(target)
    return list(found.values())


_UNITTEST_CASE_BASES = (
    "unittest.TestCase",
    "IsolatedAsyncioTestCase",
    # Classes of widely used libraries that derive from unittest.TestCase; pytest collects their
    # subclasses like any unittest case (ADR-0050).
    "django.test.TestCase",
    "django.test.SimpleTestCase",
    "django.test.TransactionTestCase",
    "django.test.LiveServerTestCase",
    "django.contrib.staticfiles.testing.StaticLiveServerTestCase",
    "rest_framework.test.APITestCase",
    "rest_framework.test.APISimpleTestCase",
    "rest_framework.test.APITransactionTestCase",
    "rest_framework.test.APILiveServerTestCase",
)


def _is_unittest_case(program: PythonProgram, class_symbol: PythonSymbol) -> bool:
    module = program.modules[class_symbol.module]
    return any(
        follow_module_alias(program.modules, _expanded_name(module, base)).endswith(
            _UNITTEST_CASE_BASES
        )
        for base in class_symbol.bases
    )


def _matches(name: str, patterns: tuple[str, ...]) -> bool:
    """pytest's name matching: a pattern with glob characters is a glob, otherwise a prefix."""

    return any(
        fnmatchcase(name, pattern)
        if any(char in pattern for char in "*?[")
        else name.startswith(pattern)
        for pattern in patterns
    )


def _with_unittest_modules(
    program: PythonProgram, collection: PytestCollection
) -> PytestCollection:
    """Also collect ``test*.py`` modules that define unittest cases (ADR-0053).

    ``python -m unittest discover`` matches ``test*.py`` by default, so ``tests_auth.py`` runs
    there although pytest's ``test_*.py`` would skip it. Whether a project runs such a module
    cannot be known statically; treating it as collected only keeps code, never reports it.
    """

    extra = tuple(
        module.path
        for module in sorted(program.modules.values(), key=lambda item: item.path)
        if PurePosixPath(module.path).name.startswith("test")
        and module.path.endswith(".py")
        and not _is_test_path(module.path, collection)
        and any(
            symbol.owner is None
            and symbol.kind is NodeKind.CLASS
            and _is_unittest_case(program, symbol)
            for symbol in module.symbols
        )
    )
    if not extra:
        return collection
    return replace(collection, files=(*collection.files, *extra))


def _is_test_path(path: str, collection: PytestCollection) -> bool:
    posix = PurePosixPath(path)
    return any(
        fnmatchcase(path if "/" in pattern else posix.name, pattern) for pattern in collection.files
    )


def _hook_implementations(program: PythonProgram, plugins: set[str]) -> set[NodeId]:
    """Top-level ``pytest_*`` functions of conftest and plugin modules; pytest calls them."""

    return {
        symbol.id
        for name, module in program.modules.items()
        if name in plugins or module.path.rpartition("/")[2] == "conftest.py"
        for symbol in module.symbols
        if symbol.owner is None and is_function(symbol) and symbol.name.startswith("pytest_")
    }


def _fixture_values(
    module: PythonModule, symbol: PythonSymbol, visible: dict[str, Fixture]
) -> set[str]:
    """Fixtures a body requests with ``request.getfixturevalue``.

    A literal name requests that fixture; a computed one may request any fixture the body sees.
    """

    names: set[str] = set()
    if "getfixturevalue" not in module.unit.source:
        return names
    for node in ast.walk(symbol.node):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "getfixturevalue"
        ):
            continue
        argument = node.args[0] if node.args else keyword_argument(node, "argname")
        value = _string_value(argument) if argument is not None else None
        if value is None:
            return set(visible)
        names.add(value)
    return names


def _reachable(roots: set[NodeId], edges: list[ExecutionEdge]) -> set[NodeId]:
    """Nodes that the fixture-resolution edges reach from the given roots."""

    successors: dict[NodeId, list[NodeId]] = {}
    for edge in edges:
        successors.setdefault(edge.source, []).append(edge.target)
    reached = set(roots)
    stack = list(roots)
    while stack:
        for target in successors.get(stack.pop(), ()):
            if target not in reached:
                reached.add(target)
                stack.append(target)
    return reached


def _requested_argument_names(
    program: PythonProgram, module: PythonModule, symbol: PythonSymbol
) -> list[str]:
    """The argument names pytest resolves for a test, as ``getfuncargnames`` computes them.

    Positional-or-keyword and keyword-only parameters without a default are requested; a
    method's first parameter is not, unless it is a static method; and the leading names that
    ``unittest.mock.patch`` decorators fill with mocks are dropped.
    """

    node = symbol.node
    assert isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    arguments = node.args
    positional = [*arguments.posonlyargs, *arguments.args]
    first_default = len(positional) - len(arguments.defaults)
    names = [
        argument.arg
        for index, argument in enumerate(positional)
        if index >= len(arguments.posonlyargs) and index < first_default
    ]
    is_static = any(_dotted_name(item) == "staticmethod" for item in symbol.decorators)
    if symbol.owner is not None and not is_static:
        names = names[1:]
    names.extend(
        argument.arg
        for argument, default in zip(arguments.kwonlyargs, arguments.kw_defaults, strict=True)
        if default is None
    )
    decorators = [*symbol.decorators, *_class_decorators(program, symbol)]
    return names[_mock_patch_arguments(program, module, decorators) :]


def _mock_patch_arguments(
    program: PythonProgram, module: PythonModule, decorators: list[ast.expr]
) -> int:
    """How many positional mocks ``patch`` and ``patch.object`` decorators pass to a test.

    A decorator may also name a patcher assigned at the top of a module, as
    ``patch_send = patch.object(Client, "send")`` in a conftest that tests import.
    """

    count = 0
    for decorator in decorators:
        expression, owner = decorator, module
        if not isinstance(expression, ast.Call):
            found = _assigned_patcher(program, module, expression)
            if found is None:
                continue
            expression, owner = found
        name = _expanded_name(owner, expression.func)
        if name.endswith("mock.patch"):
            replacement = len(expression.args) >= 2
        elif name.endswith("mock.patch.object"):
            replacement = len(expression.args) >= 3
        else:
            continue
        if not replacement and keyword_argument(expression, "new") is None:
            count += 1
    return count


def _assigned_patcher(
    program: PythonProgram, module: PythonModule, expression: ast.expr
) -> tuple[ast.Call, PythonModule] | None:
    """The call assigned to a top-level name that a decorator expression names, and its module."""

    full_name = _expanded_name(module, expression)
    owner_name, _, attribute = full_name.rpartition(".")
    owner = program.modules.get(owner_name)
    if owner is None:
        return None
    for statement in owner.tree.body:
        if (
            isinstance(statement, ast.Assign)
            and isinstance(statement.value, ast.Call)
            and any(
                isinstance(target, ast.Name) and target.id == attribute
                for target in statement.targets
            )
        ):
            return statement.value, owner
    return None


def _class_decorators(program: PythonProgram, symbol: PythonSymbol) -> list[ast.expr]:
    """Decorators of the classes around a test, innermost first; their marks apply to it."""

    decorators: list[ast.expr] = []
    owner = symbol.owner
    while owner is not None and owner in program.symbols:
        owner_symbol = program.symbols[owner]
        decorators.extend(owner_symbol.decorators)
        owner = owner_symbol.owner
    return decorators


def _marks(program: PythonProgram, module: PythonModule, symbol: PythonSymbol) -> list[ast.Call]:
    """Mark calls that apply to a test: its decorators, its classes', and ``pytestmark``."""

    expressions = [*symbol.decorators, *_class_decorators(program, symbol)]
    for statement in module.tree.body:
        if isinstance(statement, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "pytestmark"
            for target in statement.targets
        ):
            value = statement.value
            expressions.extend(value.elts if isinstance(value, (ast.List, ast.Tuple)) else [value])
    return [expression for expression in expressions if isinstance(expression, ast.Call)]


def _usefixtures_names(
    program: PythonProgram, module: PythonModule, symbol: PythonSymbol
) -> set[str]:
    names: set[str] = set()
    for expression in _marks(program, module, symbol):
        if not _expanded_name(module, expression.func).endswith("pytest.mark.usefixtures"):
            continue
        for argument in call_arguments(expression):
            value = _string_value(argument.value)
            if value is not None:
                names.add(value)
    return names


def _parameterized_names(
    program: PythonProgram, module: PythonModule, symbol: PythonSymbol
) -> set[str]:
    """Argument names that ``parametrize`` marks fill with values rather than fixtures.

    Names are a comma-separated string or a list or tuple of strings, given positionally or as
    ``argnames``. Names that ``indirect`` sends to fixtures remain fixture requests.
    """

    names: set[str] = set()
    for expression in _marks(program, module, symbol):
        if _expanded_name(module, expression.func) in HYPOTHESIS_GIVEN:
            names.update(_given_names(expression, symbol))
            continue
        if not _expanded_name(module, expression.func).endswith("pytest.mark.parametrize"):
            continue
        argnames = keyword_argument(expression, "argnames")
        if argnames is None and expression.args:
            argnames = expression.args[0]
        parsed = _argument_names(argnames)
        indirect = keyword_argument(expression, "indirect")
        if _dotted_name(indirect) == "True":
            continue
        names.update(parsed - _argument_names(indirect))
    return names


HYPOTHESIS_GIVEN = frozenset({"hypothesis.given", "hypothesis.core.given"})


def _given_names(expression: ast.Call, symbol: PythonSymbol) -> set[str]:
    """Arguments that ``@given`` fills: keywords by name, positional strategies from the right."""

    names = {keyword.arg for keyword in expression.keywords if keyword.arg is not None}
    positional = len(expression.args)
    if positional:
        parameters = [item.name for item in symbol.parameters]
        if parameters and parameters[0] in {"self", "cls"}:
            parameters = parameters[1:]
        names.update(parameters[-positional:])
    return names


LAZY_FIXTURES = ("lazy_fixture", "lazy_fixtures.lf", "lazy_fixtures.lfc", "lazyfixture")
"""Callables of pytest-lazy-fixture and pytest-lazy-fixtures that request a fixture by name."""


def _lazy_fixtures(program: PythonProgram, module: PythonModule, symbol: PythonSymbol) -> set[str]:
    """Fixtures that parametrize values request lazily, as ``lf("name")`` does."""

    names: set[str] = set()
    for expression in _marks(program, module, symbol):
        if not _expanded_name(module, expression.func).endswith("pytest.mark.parametrize"):
            continue
        for node in ast.walk(expression):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            called = _expanded_name(module, node.func)
            if called.endswith(LAZY_FIXTURES) or called.rpartition(".")[2] == "lf":
                value = _string_value(node.args[0])
                if value is not None:
                    names.update(part.strip() for part in value.split(".")[:1])
    return names


def _argument_names(expression: ast.expr | None) -> set[str]:
    if expression is None:
        return set()
    value = _string_value(expression)
    if value is not None:
        return {part.strip() for part in value.split(",") if part.strip()}
    if isinstance(expression, (ast.List, ast.Tuple)):
        items = (_string_value(item) for item in expression.elts)
        return {item.strip() for item in items if item is not None and item.strip()}
    return set()


def _pytest_plugins(
    program: PythonProgram, world: WorldId, plugin_modules: tuple[str, ...]
) -> tuple[set[str], dict[PurePosixPath, set[str]], list[Limitation]]:
    """Project modules loaded as pytest plugins, and the plugin lists that cannot be read.

    ``pytest_plugins`` names plugins by module; pytest imports each and registers its fixtures
    for every test. Names of modules outside the project belong to installed plugins. A list
    that is not literal strings may load anything, which leaves the world partial.
    """

    plugins = {name for name in plugin_modules if name in program.modules}
    scoped: dict[PurePosixPath, set[str]] = {}
    by_path = {module.path: module.name for module in program.modules.values()}
    packages = {
        PurePosixPath(module.path).parent
        for module in program.modules.values()
        if PurePosixPath(module.path).name == "__init__.py"
    }

    def base_of(conftest: PurePosixPath) -> str:
        # pytest's prepend import mode puts the directory above a conftest's outermost package
        # on sys.path, or the conftest's own directory when it is in no package.
        directory = conftest.parent
        while directory in packages and directory != directory.parent:
            directory = directory.parent
        return "" if str(directory) == "." else str(directory)

    # pytest imports a plugin by name from sys.path, which holds the root and those directories;
    # a name there may differ from the module's name under its import root, as
    # ``src.app.fixtures`` for ``app.fixtures`` when ``src`` is a regular package.
    bases = sorted(
        {
            "",
            *(
                base_of(PurePosixPath(module.path))
                for module in program.modules.values()
                if PurePosixPath(module.path).name == "conftest.py"
            ),
        }
    )

    def project_module(name: str) -> str | None:
        if name in program.modules:
            return name
        relative = name.replace(".", "/")
        for base in bases:
            prefix = f"{base}/" if base else ""
            for candidate in (f"{prefix}{relative}.py", f"{prefix}{relative}/__init__.py"):
                if candidate in by_path:
                    return by_path[candidate]
        return None

    limitations: list[Limitation] = []
    for module in program.modules.values():
        for small in module.tree.body:
            if not (
                isinstance(small, ast.Assign)
                and any(
                    isinstance(target, ast.Name) and target.id == "pytest_plugins"
                    for target in small.targets
                )
            ):
                continue
            value = small.value
            items = value.elts if isinstance(value, (ast.List, ast.Tuple)) else [value]
            names = [_string_value(item) for item in items]
            if any(name is None for name in names):
                limitations.append(
                    Limitation(
                        code="DT3202",
                        message="pytest_plugins is not a literal list of module names",
                        origin=module.node_id,
                        world=world,
                    )
                )
                continue
            declared = {
                found
                for name in names
                if name is not None and (found := project_module(name)) is not None
            }
            plugins.update(declared)
            scoped.setdefault(PurePosixPath(module.path).parent, set()).update(declared)
    return plugins, scoped, limitations


def _string_value(expression: ast.expr | None) -> str | None:
    """The string a literal evaluates to, as pytest reads it; ``"a, " "b"`` is ``"a, b"``."""

    if isinstance(expression, ast.Constant) and isinstance(expression.value, str):
        return expression.value
    return None


def _expanded_name(module: PythonModule, expression: ast.AST | None) -> str:
    dotted = _dotted_name(expression)
    if dotted is None:
        return ""
    first, *rest = dotted.split(".")
    binding = module.imports.get(first)
    if binding is None:
        return f"{module.name}.{dotted}"
    return ".".join((binding.target, *rest)) if rest else binding.target


def _keyword(call: ast.Call, name: str) -> ast.expr | None:
    return keyword_argument(call, name)


def _is_parent(parent: PurePosixPath, child: PurePosixPath) -> bool:
    return parent == child or parent in child.parents


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


def _limitation_sort_key(limitation: Limitation) -> tuple[str, ...]:
    return (
        limitation.world.key if limitation.world else "",
        limitation.code,
        str(limitation.origin or ""),
        limitation.message,
    )
