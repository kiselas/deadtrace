# Agent guide

Read `CONTRIBUTING.md` and the decision records in `docs/adr/` before semantic changes.

- Keep one active semantic milestone. The current milestone is inventory-only PR-01.
- Never import or execute target code from scanner paths.
- Do not infer future semantics from fixture expectations.
- Update `CASE.md` and `CASE.toml` only when the independent expected behavior changes.
- Do not hand-edit `uv.lock`; regenerate it with uv.
- Run Ruff, mypy, pytest with coverage, the case validator, build, and wheel smoke checks.
- Record changes to semantic invariants, trust boundaries, dependencies, or schemas in an ADR
  under `docs/adr/`, in the same pull request.
