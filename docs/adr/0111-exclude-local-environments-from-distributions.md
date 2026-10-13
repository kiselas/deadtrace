# ADR-0111: Exclude local virtual environments from distributions

**Status:** Accepted, 2026-10-13. Packaging change; model revision remains 92.

## Context

The source distribution respects `.gitignore`, which excluded only `.venv/`.
Developer environments named `.venv-3.13/` and `.venv-3.14/` therefore entered a local
source archive. CI builds from a clean checkout and does not encounter those directories.
The release receipt validated distribution identity and bytes, but accepted this content.

## Decision

Ignore versioned `.venv-*` directories and explicitly exclude `.venv*` directories from
the source distribution. Before sealing or verifying the existing receipt, inspect archive
member names and reject any `.venv` or `.venv-*` component, or a `pyvenv.cfg` component.
The latter also identifies environments with custom directory names. Do not extract or
execute archive contents for this check. The receipt schema and publication identity stay
unchanged; this strengthens validation of release inputs.

## Validation and consequences

An independently seeded checkout includes marker files under two versioned environments.
The original build includes both; the updated build must exclude both while retaining source,
tests and corpus. Build and smoke the wheel produced from that sdist. Synthetic wheel and
sdist inputs with default, versioned or custom environment names must be rejected before
writing a receipt. Existing clean artifacts still seal and verify successfully.

Scanner source, model 92 and report schemas are unchanged. Corpus report bytes must remain
identical. This guard detects recognizable environment paths; it is not a general archive
security audit or an assertion that arbitrary untracked files are safe to distribute.
