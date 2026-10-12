# ADR-0099: pytest commands in documents name test files

**Status:** Accepted, 2026-10-12; model revision 82.

ADR-0054 collects test files that a `pytest` command in a Makefile, tox configuration, CI workflow
or script names, though `python_files` would skip them. Projects also document such runs in their
README or evaluation notes:

```bash
uv run pytest -q tests/reviewer_output_contract_checks.py
```

Two reviewed cohort projects ran test files this way (seven findings, verdict false).

Markdown and reStructuredText files are now read for `pytest` commands, and only the test files
they name are taken; their other commands are examples, not deployments, and add no roots. Taking a
file as collected only keeps code, as in ADR-0054.

The case `corpus/frameworks/pytest_paths_in_readme` fails on revision 81.

MODEL_REVISION becomes `python-fastapi-dishka/82`.
