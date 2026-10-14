# ADR-0118: Collect resolver syntax projections in one module walk

**Status:** Proposed, 2026-10-14. Frontend runtime only; model revision remains 93.

## Context

Resolver initialization separately walks every module to find star imports and
nominal name rebindings. The first scope-classification query walks that same
module again to mark functions containing a walrus, global/nonlocal declaration,
or comprehension. An owned function containing 500 calls makes the same expression
payload participate in three traversals, even though these facts are independent
projections of the same immutable syntax tree.

## Decision under evaluation

Collect all three projections in one explicit worklist traversal during resolver
initialization. Retain only the existing immutable name/id sets and star-import
flag. The temporary per-module records and worklist do not outlive initialization;
there is no global cache or retained second tree.

Preserve the existing lexical boundaries: stores anywhere in the module count;
scope constructs mark all enclosing functions, including constructs in nested
classes, decorators and defaults. Class boundaries do not clear enclosing function
ids. Dotted stores whose receiver is not a name/attribute chain remain excluded.
Traversal order does not affect these set-valued projections. Scope classification
is now eager even for a module with no later query, which must be included in the
runtime measurements.

No target imports/execution, parser, framework rule, source-universe, dependency,
report schema or semantic change is introduced. Published ASTs remain immutable.
MODEL_REVISION stays 93.

## Verification and acceptance

The independent work-bound test observes one traversal of a 500-call expression
payload across initialization and repeated scope queries; the parent visits it
three times. Boundary tests check nested/async functions, nested classes, star
imports, global/nonlocal declarations, comprehensions, assignment expressions,
decorators/defaults and computed receivers.

All 358 fixed default/world-members corpus reports must remain byte-identical,
as must reviewed modern-stack text/JSON reports and seed-7 injection identities
and outcomes. Run all local quality/build/wheel gates and supported-platform CI.
Acceptance requires fresh-process alternating paired measurements including both
time and OS peak RSS. Fewer traversals alone does not prove a speed improvement.
