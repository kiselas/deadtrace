# ADR-0051: Applications built in test modules are not production worlds

**Status:** Accepted, 2026-10-06; model revision 33.

The held-out cohort review (`docs/field/`) found a library whose entire public API was reported
as "reached only from tests": its test suite builds a Flask application in `tests/conftest.py`, and
that application became the project's production world. The automatic library world exists only
when no application is found, so the library's public classes had no production root.

A framework application defined in a test module (a path `is_test_path` accepts) is a fixture for
the suite, not a deployed program. Applications found there no longer create web or framework
application worlds and do not suppress the library or script worlds. Explicitly configured worlds
and roots are unchanged, so a project that really serves an application from a test directory
names it in configuration. FastAPI applications and the other application frameworks follow the
same rule.

The case `corpus/frameworks/library_with_application_in_tests` pins the library API as
`not_candidate` with a private unreferenced control, and fails on revision 32.

MODEL_REVISION becomes `python-fastapi-dishka/33`.
