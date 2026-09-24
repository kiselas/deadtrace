# ADR-0004: One parse and one position pass per module

**Status:** Accepted, 2026-09-24. Amends the stage list of ADR-0003. The parser and position
provider are superseded by ADR-0007; the one-parse-per-module rule stays.

## Context

The PERF-01 profile (`benchmarks/results/2026-09-21-scale-50k-baseline.md`) showed that 85% of the
50k-line scan went into five independent LibCST passes per module, each building a
`MetadataWrapper` and resolving `PositionProvider`: the inventory, the frontend symbol collector,
`_collect_imports`, and the framework helpers `_top_level_assignments` and `_top_level_calls`. The
inventory and the frontend also parsed every module separately, and the first two wrappers
deep-copied the tree because they did not pass `unsafe_skip_copy=True`.

All five consumers need the same thing — source positions of nodes in one unchanged tree — and none
of them mutates the tree or relies on node identity between passes.

## Decision

1. `deadtrace.inventory.parse_source` parses a module once and builds one
   `MetadataWrapper(tree, unsafe_skip_copy=True)` whose `PositionProvider` result is resolved once.
   The result is a frozen `ParsedSource(tree, wrapper, positions)`.
2. `deadtrace.scanner.parse_collection` produces a `ParsedCollection`, mapping each unit path to its
   `ParsedSource` or to the `ParserSyntaxError` that prevented it. `analyze` builds it once, inside the
   collect stage, and passes it to `inventory_collection` and `build_python_program`.
3. Inventory and symbol collection visit through the shared wrapper, so metadata comes from its
   cache. `PythonModule.statement_lines` records the start line of every top-level small statement,
   taken from the same position pass; `_collect_imports` and the two framework helpers read it
   instead of building their own wrappers.
4. The `parsed` argument is optional everywhere. A caller that omits it gets the previous behavior,
   parsing on demand, so direct uses of `inventory_source` and `build_python_program` keep working.
5. The trees are shared and must be treated as immutable. `unsafe_skip_copy=True` is safe only under
   that rule; any future pass that transforms a tree must copy it first.
6. Sub-stages change: `collect.inventory_parse` is replaced by `collect.parse`, which covers the single
   parse and position pass of every module. `frontend.parse` is non-zero only when the frontend parses
   on demand. The benchmark artifact therefore moves to schema 3.

## Consequences

- Semantic reports are byte-identical: every case under `corpus/` and `fixtures/cases/` plus the 50k
  fixture, in both semantic and `--inventory-only` mode, was compared against `main` — 50 of 50
  identical, with identical exit codes.
- The 50k scan is 2.7 times faster at the median in a same-session comparison with `main`
  (`benchmarks/results/2026-09-24-scale-50k-single-parse.md`).
- Peak RSS grows from about 111 MB to about 166 MB on the 50k fixture, because all position maps
  coexist until the frontend has used them. That is well inside the 1 GiB budget; if it ever matters,
  the maps can be dropped per module once `statement_lines` and symbols are extracted.
- Schema-2 benchmark artifacts remain readable but are not comparable key for key with schema 3.
