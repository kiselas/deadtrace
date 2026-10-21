# ADR-0121: Routine dependency updates are batched; oracle pins move deliberately

**Status:** Accepted, 2026-10-21. Packaging and tooling only; model revision 94 and reports
unchanged.

## Context

Dependabot opens one pull request per package each week, for the `uv` lock and for pinned GitHub
Actions. `AGENTS.md` requires a recorded decision for dependency changes, and ADR-0002 recorded
one for a single Rich update. Without a standing rule each routine update waits for its own ADR,
and because every lock update rewrites `uv.lock`, merging them one by one makes the remaining pull
requests conflict. By 2026-10-21 seven such pull requests were open, the oldest from 2026-10-08.

The open updates were:

- development group, lock only: mypy 2.3.1 → 2.4.0 (with its dependency librt 0.15.0 → 0.16.0),
  ruff 0.16.8 → 0.17.0, hypothesis 6.168.0 → 6.169.0;
- runtime, lock only, inside the declared `typer>=0.20,<1`: typer 0.27.2 → 0.27.3, which escapes
  terminal control characters in error messages;
- CI: `actions/download-artifact` 8.0.1 → 8.0.2, pinned by commit in `ci.yml` and `publish.yml`;
- oracle group: fastapi 0.141.1 → 0.143.0.

The oracle group is different in kind. `fastapi==0.141.1`, `dishka==1.10.1` and `httpx==0.28.1`
are the versions the runtime oracle executes the reference application with, and
`target_environment._SUPPORTED_EXACT` names the same FastAPI and Dishka versions as tested. Corpus
manifests and generated benchmark projects declare them too. Moving the pin alone would leave the
oracle testing a version the scanner does not call tested, or, if `_SUPPORTED_EXACT` followed,
would change `DT4002` diagnostics in reports of targets that declare the old version.

The non-oracle updates were applied together with `uv lock --upgrade-package` and verified on
Windows 11 with Python 3.12: Ruff check and format, mypy with `--platform linux` and
`--platform win32`, pytest with coverage, both case validators, build and isolated wheel smoke.
Default and world-members JSON reports of all 180 corpus cases (360 reports) were hashed before
and after the update and are byte-identical. Each update had also passed the full CI matrix on its
own pull request.

## Decision

1. Updates of the development group and of pinned GitHub Actions are applied in one batch pull
   request, regenerated with uv rather than merged from the individual pull requests. They need no
   individual ADR when the full local gates and CI pass and fixed corpus reports stay
   byte-identical. Changes a new tool version forces on the source are made and described in the
   same pull request.
2. Lock-only updates of runtime dependencies that stay inside the constraints in `pyproject.toml`
   follow the same rule. They do not change what users can install. Widening or narrowing a
   runtime constraint, adding or removing a dependency, or a major version still needs its own
   ADR, as ADR-0002 did.
3. Dependabot does not propose oracle pins (`dishka`, `fastapi`, `httpx`). They are updated
   deliberately, together with `_SUPPORTED_EXACT`, corpus manifests and the oracle runs, in a pull
   request with its own ADR.

## Consequences

- Dependabot pull requests are inputs to a periodic batch, not merge candidates. After a batch
  merges, Dependabot closes the pull requests the lock already satisfies.
- A batch that changes any corpus report is not routine and needs its own decision.
- The FastAPI 0.143.0 update is not applied; the oracle stays at FastAPI 0.141.1 until a
  deliberate oracle update.
