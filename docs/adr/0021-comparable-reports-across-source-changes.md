# ADR-0021: Reports stay comparable across ordinary source changes (model revision 15)

**Status:** Accepted, 2026-09-28.

## Context

The fifth audit pass ran the CI workflow of P6 on real history: three local checkouts were
exported at `HEAD~30` and `HEAD` with `git archive`, the old report became a baseline, and the new
scan applied it with `--fail-on-new`. It never passed.

- **Every change of roots was a method change.** The method descriptor held each world's roots,
  and test functions, routes, and scripts are roots, so a baseline was `incomparable` after any
  commit adding a test and `--fail-on-new` exited 2. `compare` reported such reports as
  `partially_comparable`, so `compare --fail-on-new` exited 2 as well. A minimal FastAPI project
  showed it after one added test; the fingerprints themselves were unchanged.
- **Every dependency and analyzer release was a method change.** The descriptor held the exact
  version of every imported package from `uv.lock` and the analyzer version, so an update of any
  dependency, such as a routine `httpx` release, or of Deadtrace made the baseline incomparable,
  although only FastAPI and Dishka versions affect the model, and only outside the supported
  ranges (ADR-0018).
- **The capability set depended on the source.** `pytest.fixtures` was listed only when the
  project had tests, so a project's first test changed the method.
- **Fingerprints hashed the worlds** (ADR-0019), so a new application renewed every fingerprint
  and `baseline update` dropped every reviewed entry.
- **A report of a mid-sized project could not be read back.** Each finding's explanation copied
  every world's limitations; with hundreds of guards per world, a 476-file project wrote a 39 MB
  report, beyond the 16 MB artifact limit, so `baseline create`, `compare`, and `explain` failed
  on it. Explanations were also built by scanning every symbol and every edge per finding. A
  624k-line monorepo wrote 143 MB, as each of its worlds listed tens of thousands of guards.
- **Input issues never matched a saved baseline.** They were stored as tuples and read back as
  lists, so a report with any input issue was incomparable with its own baseline.

## Decision

1. **Method.** Two reports, or a report and a baseline, have the same method when they agree on
   the report schema, the model revision, the configuration digest, the capability set, the
   analysis state, the input issues, and the target dependency issues that weaken the model
   (`DT4001`; an untested version in range, `DT4002`, does not). Worlds, roots, retained and
   conservative roots, exact dependency versions, and the analyzer version follow from the
   source or do not change semantics; semantic changes bump the model revision. The analysis
   state and the input issues stay in the method although sources cause them: a degraded
   analysis cannot vouch for the absence of findings, so a commit that adds a syntax error makes
   `--fail-on-new` exit 2 rather than 1. `compare` lists added and removed worlds and roots of
   common worlds beside the source files; reports without a common world stay `incomparable`.
2. **Capabilities** are the fixed list of the model revision; `pytest.fixtures` is listed
   whether or not the project has tests.
3. **Fingerprints** hash the finding's code and the identities of its members only.
4. **Baselines.** An incomparable baseline names the differing method fields in the report
   (`baseline.reasons`) and on standard error. `baseline update` carries a reviewed entry over to
   a finding with its fingerprint or, after a method change renewed the fingerprint, with its
   code and exactly its members, and records the new fingerprint and members.
5. **Explanations.** A finding's explanation lists each world's limitations other than
   conservative guards once, with their count, and the number of guards; a guard keeps code
   possibly running, so none applies to an unreached member, and the world's entry in the report
   still lists each of them. Symbols and outbound edges are indexed once per report.
6. **Report size.** Deadtrace reads its own reports and baselines up to 256 MiB; project inputs
   such as `uv.lock` keep the 16 MiB limit. `scan` warns when a written report exceeds what
   `baseline`, `compare`, and `explain` read. Listing each guard and conservative definition once
   per report instead of once per world is left to a later report schema.
7. **Schema.** The report, baseline, and comparison schemas stay at version 1, which is
   pre-alpha (the changelog's compatibility note): finding explanations list non-guard
   limitations with a `count` and add `guard_count`; a baseline's `method` object loses
   `tool_version`, `worlds`, and `target_environment_digest` and gains `target_environment`;
   `baseline` in an annotated report gains `reasons`; a comparison gains `worlds`. Baselines of
   earlier versions differ in their model revision anyway and are refreshed with
   `baseline update`.

`MODEL_REVISION` becomes `python-fastapi-dishka/15`, together with the modeling changes of
ADR-0022.

## Consequences

- On a FastAPI and Dishka service, a service of 476 files, and a Django project, a baseline of
  `HEAD~30` applied to `HEAD` is comparable and accepts every unchanged finding (18, 53, and 5);
  the new findings (3, 7, and 10) are code whose callers the thirty commits removed and, in the
  Django project, tests in files that its explicit `python_files` list does not collect; the
  resolved ones (0, 13, and 52) were deleted. Each was checked against the source. `compare` is
  `comparable`, with 95, 42, and 47 added roots listed as source changes.
- Reports of the audited single-service projects are 1.2 to 10 times smaller, 35.1 MB to 3.5 MB
  on the largest, and all stay below 16 MiB. The monorepo's report fell from 143 MB to about
  60 MB with this decision alone, and grew again with the worlds that ADR-0022 adds per service
  worker, so it needs the 256 MiB limit.
- Unit tests in `tests/test_comparison.py` and `tests/test_cli.py` cover comparability across
  new roots, worlds, dependency and analyzer versions, input issues, renewed fingerprints, the
  reasons of an incomparable baseline, and the size warning.
- Every fingerprint changes once with this revision, and baselines written before it are
  incomparable because the model revision changed; `baseline update` carries their entries over
  by code and members.
- A change of the analyzer that alters results without a model revision would now go unnoticed
  by comparison; the contribution rules already require the revision bump. Capability revisions
  need not change with it, since the model revision is part of the method.
- The identity of an automatic world includes its application's module, so renaming the module
  of the only application leaves two reports without a common world, `incomparable`; a
  configured world keeps its name.
