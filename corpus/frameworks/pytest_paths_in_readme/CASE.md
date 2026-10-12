# Test files named by a pytest command in a README

`README.md` documents `uv run pytest -q tests/contract_checks.py`. The file does not match pytest's
`python_files`, but the command collects it, so `test_contract` is not a candidate. `never_run.py`
is named nowhere. The `uvicorn app:app` example in the same README adds no application.
