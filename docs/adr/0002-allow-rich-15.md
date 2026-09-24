# ADR-0002: Allow Rich 15 as the rendering dependency

**Status:** Accepted, 2026-09-21. Retroactive: the change was merged as pull request #3 before
`docs/adr/` existed (see ADR-0001); this record documents the verification that preceded the merge.

## Context

`pyproject.toml` declared `rich` as a direct runtime dependency with the constraint `rich>=14,<15`.
Deadtrace does not import Rich anywhere in `src/` or `tests/`; the only consumer is Typer, which
renders `--help`, usage errors, and command panels with it. Typer 0.27.2 itself requires only
`rich>=13.8.0` with no upper bound, so the Deadtrace constraint is the only thing that keeps a new
Rich major version out of the CLI.

Dependabot proposed widening the constraint to `rich>=14,<16` and updating `uv.lock` from 14.3.4 to
15.0.0. `AGENTS.md` requires a recorded decision for dependency changes, and a rendering library
affects user-visible output and, through Typer, the CLI's error presentation.

Rich 15.0.0 (2026-04-12) lists one breaking change — dropping Python 3.8 support — and four fixes:
empty `print` honoring `end`, `Text.from_ansi` preserving newlines, `FileProxy.isatty` proxying, and
inline code in Markdown table cells. The fixes correct previously incorrect behavior rather than
change rendering APIs, and Deadtrace requires Python 3.12, so the breaking change does not apply.

Before merging, the following was verified locally on Windows 11 with the Rich 15 lock and with the
mypy 2.3.1 lock from pull request #2 merged in, because the two pull requests' CI runs had never
seen each other's changes:

- `uv sync --locked --all-groups` succeeded, so the merged `uv.lock` is consistent with
  `pyproject.toml`;
- `uv run mypy` and `uv run mypy --platform linux` reported no issues;
- `uv run pytest --cov`: 139 passed, 1 skipped, coverage 90.38%, unchanged from the baseline,
  including `test_help_and_version`, which asserts on rendered `--help` content;
- `deadtrace cases validate corpus`: 18 cases, 51 lexical targets, 18 semantic manifests;
- `deadtrace scan corpus/reference/fastapi_dishka_basic` produced the same finding with the same
  fingerprint `rch003-a8d82a0e9b1c655b`; `deadtrace doctor` and `deadtrace --help` rendered
  correctly by inspection.

After the merge, the `main` CI run passed on Ubuntu and Windows. Machine-readable output
(`--format json`) does not pass through Rich at all, so report compatibility was never at risk.

## Decision

Accept `rich>=14,<16` as the runtime constraint and Rich 15.0.0 in `uv.lock`. Keep `rich` as a
direct dependency even though it is not imported: its purpose is to bound the version Typer renders
with, since Typer's own constraint has no upper bound. Dropping the direct dependency is rejected
for that reason.

Future Rich major versions follow the same procedure: the full repository gate plus a by-eye check
of `scan`, `doctor`, and `--help` text output, recorded in a superseding ADR.

## Consequences

- Rendered text output is now produced by Rich 15. No difference was observed in the checks above,
  but presentation is not covered by a golden-output test, so a subtle change would be caught only
  by the assertions in `test_help_and_version`.
- The constraint can be narrowed back to `<15` with a one-line change and a lock refresh if a
  regression is found; no code depends on Rich 15 features.
