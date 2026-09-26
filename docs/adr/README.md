# Architecture decision records

Decision records explain why Deadtrace behaves, is built, or is constrained the way it is. They are
kept here, next to the code they justify, so that a decision and the change implementing it travel
in the same commit and the same review. ADR-0001 records that choice.

## When an ADR is required

`AGENTS.md` and `GOVERNANCE.md` require a recorded decision for changes to semantic invariants, the
trust boundary, dependencies, or stable schemas. Add one in the same pull request as the change.
Changes to architecture, supported scope, or roadmap status should also be recorded when the
reasoning would otherwise survive only in a pull request thread.

## Format

One file per decision, `NNNN-short-slug.md`, numbered in order of acceptance, with these sections:

- **Status** — `Proposed`, `Accepted`, `Superseded by ADR-NNNN`, or `Deprecated`, with the date.
- **Context** — the facts that made a decision necessary, including what was verified and how.
- **Decision** — what was decided, stated so that a reader can check the code against it.
- **Consequences** — what becomes easier, harder, or newly required, including follow-up work.

An accepted ADR is not edited to change its meaning; a new ADR supersedes it and the two link to
each other. Typo and link fixes are fine.

## Index

- [ADR-0001](0001-decision-records-in-repository.md) — Decision records live in the repository.
  Accepted.
- [ADR-0002](0002-allow-rich-15.md) — Allow Rich 15 as the rendering dependency. Accepted,
  retroactive.
- [ADR-0003](0003-pipeline-stage-instrumentation.md) — Sub-stage instrumentation and
  benchmark artifact schema 2. Accepted; stage list amended by ADR-0004.
- [ADR-0004](0004-single-parse-per-module.md) — One parse and one position pass per module.
  Accepted.
- [ADR-0005](0005-indexed-symbol-lookups.md) — Indexed symbol lookups instead of linear scans.
  Accepted.
- [ADR-0006](0006-known-violation-cases.md) — Known contract violations are recorded as pinned
  failing cases. Accepted.
- [ADR-0007](0007-stdlib-ast-frontend.md) — The analysis parses with the standard-library `ast`
  module. Accepted; supersedes the parser choice of ADR-0004.
- [ADR-0008](0008-python-core-soundness.md) — Python-core soundness rules (model revision 5).
  Accepted.
- [ADR-0009](0009-implicit-dispatch-and-names.md) — Implicit dispatch, external base hooks, and
  modules named by strings (model revision 6). Accepted.
- [ADR-0010](0010-module-execution.md) — Module execution and import bindings (model
  revision 7). Accepted.
- [ADR-0011](0011-automatic-worlds.md) — Automatic worlds for scripts, applications, and
  libraries (model revision 8). Accepted.
- [ADR-0012](0012-library-hooks-and-escaped-classes.md) — Overloads, library hooks,
  branch-bound functions, and escaped classes (model revision 9). Accepted.
- [ADR-0013](0013-django-installed-apps.md) — Django installed applications (model revision
  10). Accepted.
- [ADR-0014](0014-declarative-world-frameworks.md) — The frameworks of a configured world are
  declarative. Accepted.
- [ADR-0015](0015-source-discovery-and-import-roots.md) — Source discovery skips environments;
  `src` packages and script-directory import roots. Accepted.
- [ADR-0016](0016-world-local-pytest-facts.md) — pytest facts are local to the tests world, and
  pytest's own name resolution. Accepted.
- [ADR-0017](0017-conventions-found-by-the-field-audit.md) — Conventions found by the field audit
  (model revision 11). Accepted.
- [ADR-0018](0018-second-field-audit.md) — Source exclusions, supported version ranges, and
  CLI commands (model revision 12). Accepted.
- [ADR-0019](0019-third-field-audit.md) — Wrapped application factories, plugin libraries, and
  build copies (model revision 13). Accepted.
