# Contributing to Deadtrace

Deadtrace aims to make unusually careful claims about code that may be removed. Changes are
welcome, but semantic correctness and honest limitations matter more than detector count.

## Before writing code

- Use an existing issue for bounded fixes and documented roadmap work.
- Discuss new language support, framework models, report-schema changes, and dependencies in an
  issue before implementation. These choices create long-term compatibility obligations.
- Every semantic change needs a minimal real pattern, an expected useful outcome, a negative
  case, and a way to evaluate it independently from Deadtrace's own output.

## Local setup

Install uv, clone the repository, then run:

```console
uv sync --locked --all-groups
uv run deadtrace cases validate fixtures/cases
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest --cov
uv build
```

CI runs the suite on Windows and Linux and installs the built wheel outside the source tree.

## Architecture boundaries

- Scanner code must never import or execute target code.
- The source universe is distinct from what is visible in reports.
- Unknown behavior is explicit and propagates through the execution domains it can affect.
- Framework knowledge lives behind semantic capabilities; target frameworks are not scanner
  runtime dependencies.
- Machine output goes to stdout. Diagnostics go to stderr.
- Do not add caches, services, plugin loaders, or parsers without a measured case and an ADR.

## Tests and fixtures

Tests under `tests/` verify the analyzer. Files under `fixtures/cases/` are target programs and
may intentionally contain patterns that ordinary linters dislike. A case consists of:

- `CASE.md`, explaining the independent semantic expectation and the unsafe outcome;
- `CASE.toml`, naming lexical targets without copying analyzer output;
- target source files.

Do not turn future semantic expectations into passing tests until the semantics exist.

A present violation of the analysis contract, such as a candidate reported for code that may run in
a complete world, is recorded as a case under `fixtures/known-violations/` and pinned in
`tests/test_known_violations.py` before any fix; see that directory's README and ADR-0006.

## Pull requests

Keep changes focused. In the description, state the user-visible result, test plan, limitations,
and any report/config compatibility impact. When a change alters architecture, analysis
semantics, supported scope, dependencies, or roadmap status, add or supersede a decision record
in `docs/adr/` in the same pull request; see `docs/adr/README.md`.

By participating, you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md).
