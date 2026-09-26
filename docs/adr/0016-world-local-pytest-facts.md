# ADR-0016: pytest facts are local to the tests world

**Status:** Accepted, 2026-09-26.

## Context

Invariant 5 of the roadmap says that state is world-local and that tests do not leak facts into
applications. The pytest model broke it: the edges from a test to the fixtures it requests, and
the unknown boundaries for fixtures it could not resolve, were added to the shared graph. An
unresolved fixture's boundary targets the whole graph, so whenever a production world reached a
test conservatively, for example through a script that imports modules by a computed name, it
inherited that boundary. On the audited FastAPI and Dishka service the scripts world reached
5,262 of 5,949 nodes this way and no candidate could be reported.

The model was also far from what pytest resolves. It treated every parameter as a fixture request,
including parameters with defaults and those filled by `unittest.mock.patch`, read only the first
positional `parametrize` argument, ignored marks on classes and `pytestmark`, did not see
fixtures imported into a module or registered by `pytest_plugins`, and marked any
`pytest_plugins` assignment as unmodeled. The tests world was partial on every audited project,
which also withheld every `RCH004` finding.

## Decision

1. **World-local facts.** `WorldPlan` carries `edges` and `boundaries` that hold only in that
   world. The pytest model puts fixture resolution and unresolved-fixture boundaries there; the
   shared graph keeps only declaration retention.
2. **Requested names** follow pytest's `getfuncargnames`: positional-or-keyword and keyword-only
   parameters without defaults, without the first parameter of a method that is not a static
   method, and without the leading parameters that `patch` and `patch.object` decorators fill.
3. **Parametrized names** come from `parametrize` marks on the test, on its classes, and in a
   module's `pytestmark`, given as a comma-separated string or a list or tuple of strings,
   positionally or as `argnames`; names that `indirect` sends to fixtures stay requests. A name
   any test parametrizes may fill an argument of a fixture, and a `pytest_generate_tests` hook in
   the module or a conftest above it may give any unresolved argument a value.
4. **Visibility.** A module's namespace holds the fixtures it defines and those it imports by
   name or with `*`; a test sees its plugins' fixtures, then its conftests' from the outside in,
   then its own module's. Project modules named by a literal `pytest_plugins` list or registered
   as `pytest11` entry points are plugins. A computed `pytest_plugins` stays unmodeled
   (`DT3202`).
5. **Collection.** `python_files`, `python_classes`, and `python_functions` are read from the
   first of `pytest.ini`, `pyproject.toml`, `tox.ini`, and `setup.cfg` that configures pytest.
   A collected class and every project class it inherits test methods from are collected;
   `unittest.TestCase` hierarchies collect methods whose names start with `test`.
6. **Roots.** Collected classes, `pytest_*` hooks of conftests and plugin modules, xunit-style
   setup and teardown methods and functions, and project fixtures that override a fixture of a
   widely used plugin, such as `event_loop`, are roots of the tests world. A fixture of such a
   plugin that the project does not define is resolved outside the project, not an unknown
   boundary. An unresolved argument of a fixture that no test can reach limits nothing.
7. **Test code.** A path is test code when a directory on it is `test`, `tests`, or `testing`,
   ends with `_test` or `_tests`, or starts with `test_` or `tests_`, when it is a `conftest.py`
   or a `test_*.py` or `*_test.py` file, or when it lies below a directory, other than the root,
   that holds a `conftest.py`. `RCH004` never reports test code.

The `pytest.fixtures` capability becomes revision 2.

## Consequences

- On five audited projects the tests world became complete; `RCH004` findings appear where
  production code is used only by tests. `tests/test_pytest_semantics.py` checks each rule,
  including that an unresolved fixture no longer protects code in a production world.
- `corpus/frameworks/pytest_hooks_and_configuration` records hooks, an overriding plugin fixture,
  and a configured `python_files` that leaves a `test_*.py` module uncollected.
- pytest's `rootdir` search for configuration files in parent directories and `testpaths` are
  not modeled; configuration is read at the scan root.
