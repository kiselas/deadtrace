# ADR-0061: GitHub workflow steps are command files

**Status:** Accepted, 2026-10-07; model revision 43.

ADR-0054 collects test files that a `pytest` command names, in Makefiles, tox files, and scripts.
Source discovery skips directories whose names start with a dot (ADR-0015), so
`.github/workflows/*.yml`, where many projects keep `pytest tests.py`, was never read: 93 reviewed
members of one cohort project were reported as unreached for that reason.

The deployment reader now also walks `.github` at the project root and its `workflows`
directory, and reads their `*.yml` and `*.yaml` files as command files. No other dot-directory is
read, and these files are not Python source. `python -m pytest <file>` is read like `pytest <file>`.
Both rules only add references that keep code; they report nothing.

The case `corpus/frameworks/pytest_explicit_path_in_workflow` fails on revision 42.

MODEL_REVISION becomes `python-fastapi-dishka/43`.
