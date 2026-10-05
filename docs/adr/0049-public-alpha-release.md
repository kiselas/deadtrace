# ADR-0049: Publish an exact-commit read-only alpha

**Status:** Accepted, 2026-10-05; owner requested publication and configured a PyPI pending publisher.

## Context

The repository still described inventory-only PR-01 and deferred publication, although accepted
ADRs through 0046 and recorded tests establish a substantially broader static analyzer. The owner
requested a public release using verified artifacts and OIDC publishing.
The working checkout also contains unfinished model-32 edits, which must not enter a release
implicitly. The selected committed base is ed7e105, whose scanner model is 31 and whose independent
attribute-store recall gap is deliberately pinned without a semantic fix.

## Decision

The one active milestone is public read-only alpha 0.1.0a1 for Python 3.12, freezing scanner
semantics at model 31. Supersede the inventory-only active-milestone instruction and historical
publication deferral; retain the dated roadmap snapshot as history. Document the analysis contract,
architecture and support limits alongside release acceptance. No scanner behavior, target-execution
boundary, runtime dependency constraint or public analysis schema changes in release preparation.

CI builds exactly one wheel and one sdist, records the full commit, version and each file's SHA-256
and size in `release-receipt.json` (internal release receipt schema 1), and uploads them under a
commit-specific artifact name. Both Linux and Windows smoke jobs install the same CI-built wheel
outside the checkout. Publication is manually dispatched from main with a version tag and CI run
ID. Require a completed successful main push run of ci.yml at the exact tagged commit, the tag's
version matching pyproject.toml, ancestry in main, and matching distribution metadata and checksums.
Transfer those verified bytes to a separate Ubuntu publication job; do not rebuild. Only that job
has id-token:write and uses PyPI Trusted Publishing with environment pypi. Workflow action versions
are pinned to commits. Run concurrency prevents overlapping publication attempts for one tag.

## Consequences

Alpha APIs/schemas can evolve; complete analysis means the analyzer's modeled contract under given
inputs, not proof of arbitrary Python behavior or deletion safety. Known recall gaps remain explicit.
The selected model-32 refinement needs its own verified release. All local repository gates and
hosted Linux/Windows CI must pass on the release candidate before tagging/publishing. GitHub Release
records the commit and CI run and attaches the same wheel, sdist and receipt. A final PyPI-installed
wheel smoke confirms public installation and no target execution. No token is stored in repository
secrets. The pending publisher supplied by the owner currently permits any environment; binding it
to pypi can subsequently narrow that identity without changing the release bytes.
