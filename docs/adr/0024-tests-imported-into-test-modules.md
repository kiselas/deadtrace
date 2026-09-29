# ADR-0024: Tests imported into a test module are collected there (model revision 17)

**Status:** Accepted, 2026-09-29.

## Context

The sixth field pass scanned projects that no earlier pass had seen. A UI test suite ran once with
per-test browser contexts and once with a session-scoped context for comparison. The second
directory held a `conftest.py` that redefines the four fixtures the suite requests, and one test
module that repeats the suite with `from tests.ui_tests.configurator.test_infrastructure import *`.
The analyzer reported the four fixtures of the second `conftest.py` as unused.

They run. pytest collects the functions and classes that a module's namespace binds, wherever they
are defined, so the imported tests are collected in the importing module and resolve their
fixtures from the importer's directory: its `conftest.py` files and its namespace, not those of the
module that defines the tests. The analyzer resolved fixtures only from the directory of the
module that defines a test.

## Decision

1. A test module, matched by `python_files`, that binds project functions or classes from other
   modules by name or by `*` (transitively, without names that start with an underscore) collects
   those whose local name matches `python_functions` or `python_classes`, or that derive from
   `unittest.TestCase`, as tests of its own. A class brings the methods of its project bases.
2. Such a test requests its fixtures once for each module that collects it: its defining module,
   when that is a test module or the test is collected by the old rule, and every importing
   module. A fixture is visible from a context when its `conftest.py` is at or above the context's
   directory, or it is in the context module's namespace (ADR-0022). The importing module is a
   root of the tests world.
3. A directory without Python files reports `no Python source files were found below the root`
   instead of `no execution roots were found`.

`MODEL_REVISION` becomes `python-fastapi-dishka/17`.

## Consequences

- The four fixtures are no longer reported, and the other 26 findings of that project (unused
  fixtures and helpers) were checked in the source and are correct. A test collected through an
  import only adds edges in the tests world, so it can hide findings but not create them.
- `corpus/frameworks/pytest_imported_suite` fails on revision 16.
- Not modeled: `__all__` in the imported module, which limits what `*` binds; imports inside
  functions or `if TYPE_CHECKING` blocks are bound like any other import.
- Scripts that run code at import and have no main guard are still not roots unless a deployment
  command names them (ADR-0023); a function defined in such a script is reported when nothing
  else reaches it.
