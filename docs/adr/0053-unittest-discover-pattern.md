# ADR-0053: `test*.py` modules with unittest cases are collected

**Status:** Accepted, 2026-10-06; model revision 35.

The tests world collects modules by pytest's `python_files` (default `test_*.py`, `*_test.py`).
`python -m unittest discover` uses `test*.py`, so a project whose runner is unittest and whose
modules are named `tests_*.py` had every test class reported as unreached: 56 reviewed members
in one cohort project.

A module whose file name matches `test*.py`, is not already collected, and defines a
`unittest.TestCase` class (including the bases of ADR-0050) is collected as a test module. Which
runner a project uses is not known statically; treating the module as collected keeps code and
never reports it, so the rule is safe in the conservative direction. Modules without a unittest
case are unchanged, since pytest would not collect them and unittest would find no tests.

The case `corpus/frameworks/unittest_discover_pattern` fails on revision 33.

MODEL_REVISION becomes `python-fastapi-dishka/35`.
