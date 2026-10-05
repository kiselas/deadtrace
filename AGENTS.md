# Agent guide

Read `CONTRIBUTING.md` and the decision records in `docs/adr/` before semantic changes.

- Keep one active milestone. The current milestone is stabilization toward 0.1.0b1: scanner
  semantics stay at model 31 unless a change has its own independent case, ADR, and revision bump.
  Inputs, runtime versions, CLI robustness, and documentation changes keep corpus reports
  byte-identical.
- Never import or execute target code from scanner paths.
- Do not infer future semantics from fixture expectations.
- Update `CASE.md` and `CASE.toml` only when the independent expected behavior changes.
- Do not hand-edit `uv.lock`; regenerate it with uv.
- Run Ruff, mypy, pytest with coverage, the case validator, build, and wheel smoke checks.
- Record changes to semantic invariants, trust boundaries, dependencies, or schemas in an ADR
  under `docs/adr/`, in the same pull request.
