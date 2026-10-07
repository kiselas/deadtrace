# ADR-0054: Test files named in `pytest` commands are collected

**Status:** Accepted, 2026-10-07; model revision 36.

pytest collects a file passed as an argument whatever `python_files` says. Projects run
`pytest tests.py` or `pytest checks/smoke.py` from a Makefile, tox, or a script, and the tests
world skipped such files, so every test and every helper reached only from them was reported as
unreached: 154 reviewed members in one cohort.

The deployment reader (ADR-0023) already tokenizes commands in Makefiles, scripts, Dockerfiles,
and tox. A `pytest` or `py.test` command now records each `*.py` argument, with any `::node` suffix
removed, as a `test_path` reference. These paths are added to the collected-file patterns, as ADR-0053
does for `test*.py` unittest modules. Which command a project really runs is not known statically;
treating a named file as collected only keeps code, never reports it. `test_path` references do not
create a deployment world. Commands in `.github/workflows` were not read at first (ADR-0015); ADR-0061 reads them.

The case `corpus/frameworks/pytest_explicit_test_path` fails on revision 35.

MODEL_REVISION becomes `python-fastapi-dishka/36`.
