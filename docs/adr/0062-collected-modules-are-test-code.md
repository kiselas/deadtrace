# ADR-0062: Modules the tests world collects are test code

**Status:** Accepted, 2026-10-07; model revision 44.

Production-side classification treats a file as test code by pytest's name and directory
conventions (ADR-0017). A file that the tests world collects by another route, such as `tests.py`
run by `pytest tests.py` (ADR-0054, ADR-0061) or a `test*.py` unittest module (ADR-0053), was
still production code to it. Once those files were collected, their classes became
"Production code is reached only from tests" (RCH004) findings: 18 of 19 findings of one cohort
project, each false.

`collected_test_paths` returns the paths of the modules the tests world collects, and
`build_findings` excludes their nodes from RCH004 candidates like any other test file. The set only
removes candidates; no execution edge changes.

The case `corpus/frameworks/pytest_explicit_test_path` (its module is now the private
`_checks.py`, outside the library world) fails on revision 43.

MODEL_REVISION becomes `python-fastapi-dishka/44`.
