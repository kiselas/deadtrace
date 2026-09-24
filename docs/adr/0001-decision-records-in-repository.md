# ADR-0001: Decision records live in the repository

**Status:** Accepted, 2026-09-21.

## Context

Six repository documents — `AGENTS.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `GOVERNANCE.md`,
`README.md`, and `ROADMAP.md` — referred to a "companion wiki" as the home of the analysis
contract, architecture notes, support matrix, the A01–A40 acceptance matrix, and architecture
decision records. On the status date that wiki existed nowhere: the GitHub wiki feature was
disabled for the repository, no `deadtrace.wiki.git` repository had been created, and no
`deadtrace_wiki` directory existed beside the checkout. The documents described content that could
not be read, and `AGENTS.md` required ADRs that had no place to be written.

Two properties of the project decide where that material should live.

First, the roadmap's non-negotiable invariants tie semantic changes to their documentation: a
semantic change must increment `MODEL_REVISION` and update corpus expectations and support claims
together (invariant 8), and the definition of done requires support, limitation, schema, and
changelog documents to be updated with the change. A decision record stored outside the repository
cannot be reviewed in the same diff, cannot be required by CI, and drifts from the code the moment
either side changes alone.

Second, the project is set up for outside contributors — `CONTRIBUTING.md`, `GOVERNANCE.md`, a code
of conduct, and an Apache-2.0 license. A GitHub wiki does not take pull requests, and a private
directory beside the checkout is invisible to anyone but the maintainer.

The same reasoning that argues against an external home for public reasoning argues for one in a
different case. The roadmap's P3 stage is an authorized pilot on a real, private project. Its triage
notes, real findings, module names, and any third-party source must not enter a repository that is
intended to become public.

## Decision

Architecture decision records live in this repository under `docs/adr/`, one file per decision,
numbered in order of acceptance, and are added in the same pull request as the change they
justify. The format and index are described in `docs/adr/README.md`.

The other documents formerly attributed to the companion wiki — the analysis contract, architecture
notes, support matrix, and acceptance matrix — belong under `docs/` in this repository as well.
Until each is written, repository documents state that it is pending rather than pointing to a
location where it does not exist.

Material from authorized pilots on private projects, and any note that names third-party code,
stays outside the repository in a private companion workspace. Repository documents may refer to
such material only by an opaque identifier.

## Consequences

- `AGENTS.md`, `GOVERNANCE.md`, and `CONTRIBUTING.md` name `docs/adr/` as the place for a recorded
  decision, so the requirement is checkable during review.
- The `CHANGELOG.md` entry claiming A01–A40 acceptance traceability "in the companion wiki" is
  removed; the traceability map has not been published and the changelog should not say it was.
  `ROADMAP.md` keeps its A-numbers and states that their definitions are pending.
- ADR-0002 is the first substantive record and is retroactive: it documents a dependency change
  merged on the day this decision was taken, before there was a place to record it.
- Writing the analysis contract, architecture notes, support matrix, and acceptance matrix is
  follow-up work. Their absence is now visible instead of implied.
