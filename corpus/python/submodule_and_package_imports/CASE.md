# Submodules and package initializers

`main` runs `import jobs.nightly`, which runs `jobs/__init__.py` and then
`jobs/nightly.py`; the latter calls `register` at its top level. The world root is
`jobs.cli:main`, and Python runs the `jobs` package before its `cli` submodule, so
`configure_logging` in the package initializer runs too. Reporting `register` or
`configure_logging` as unreached is unsafe. `jobs.nightly.unused_job` is never called and
must stay a candidate.

Recorded as a known violation of the analysis contract (ADR-0006) and met from model
revision `python-fastapi-dishka/7` (ADR-0010).
