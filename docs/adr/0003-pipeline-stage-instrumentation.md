# ADR-0003: Sub-stage instrumentation and benchmark artifact schema 2

**Status:** Accepted, 2026-09-21.

## Context

Roadmap item PERF-01 requires sub-stage timings that separate discovery, stable snapshot reads, CST
parsing and metadata, symbol collection, import resolution, flow extraction, framework modeling,
finding construction, and reporting, plus a benchmark artifact that records the host, tool
versions, and size counters — without changing analysis semantics and without target source, paths,
or user names entering the artifact.

Before this change the pipeline exposed three wall-clock numbers (collect, frontend, solve) and the
schema-1 benchmark artifact carried only digests and those three stages. The first CPU profile of
the 50k-line fixture showed that neither number located the cost: LibCST parsing was a small
fraction, file discovery and snapshot verification were negligible, and the bulk was LibCST
metadata resolution repeated for every module across the inventory, frontend, and framework passes.
Reaching that conclusion required a separate cProfile run; the artifact could not show it.

## Decision

1. `deadtrace.timing.StageTimings` is the single instrumentation collector. It holds a fixed set of
   sub-stage names (`STAGES`) and counters (`COUNTERS`); an unknown name is a programming error and
   raises. `analyze` creates one collector per run and threads it through `collect_sources`,
   `inventory_collection`, `inventory_source`, `build_python_program`, and `build_framework_model`
   as an optional keyword argument. Callers that pass nothing get a throwaway collector, so the
   public functions keep their existing behavior.
2. Instrumentation is additive only. It wraps existing statements in `with timings.stage(...)` and
   adds counters; it never reorders work, caches results, or changes what a stage computes. The
   semantic report does not include timings, so report determinism is unaffected. Corpus reports
   were verified byte-identical before and after the change.
3. Sub-stage names carry the top-level stage whose wall time contains them as a prefix, so the
   invariant "sub-stages nested in a stage sum to at most that stage" is testable. LibCST metadata
   resolution and symbol collection share one sub-stage, `frontend.symbols`, because LibCST resolves
   metadata lazily inside the same visitor pass; separating them would change how the frontend
   walks the tree, which is optimization work, not measurement.
4. The benchmark artifact moves to schema 2. It adds `descriptor.deadtrace_version` and
   `descriptor.libcst_version`; a `host` block with system, release, machine, and Python
   implementation and version but no host name; deterministic `counters`; per-sample `stages` and
   `report_seconds`; per-sub-stage `summary.stages`; and `volatile_fields`, naming exactly which
   fields may differ between runs or hosts. `total_seconds` keeps its schema-1 meaning (analysis
   only) and `report_seconds` is separate. `memory_note` becomes `notes.memory`.
5. Timed runs never enable `tracemalloc`. CPU profiles are taken in a separate process with
   `benchmarks/profile_scan.py`, and only path-sanitized excerpts are committed.

## Consequences

- Performance work can be judged from the artifact alone. The first schema-2 measurement of the
  50k fixture attributes more than four fifths of wall time to the five per-module
  `MetadataWrapper`/`PositionProvider` passes and well under one percent to file discovery, reading,
  and snapshot verification; the exact figures are in `benchmarks/results/`. PERF-02 as written
  targets collection I/O and should be re-stated against these numbers before any optimization.
- Every benchmark artifact produced before this change is schema 1 and is not comparable field by
  field with schema 2. No schema-1 artifact was ever committed, so nothing needs migrating.
- Adding a sub-stage or counter means adding its name to `STAGES` or `COUNTERS`, which changes the
  artifact key set and therefore needs a changelog entry.
- The collector costs two `perf_counter` calls per stage entry. Per-module stages add on the order
  of a millisecond to a 251-module scan; per-symbol flow extraction is timed as one block, not per
  symbol.
