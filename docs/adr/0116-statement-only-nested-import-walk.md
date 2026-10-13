# ADR-0116: Visit statement containers when finding nested module imports

**Status:** Proposed, 2026-10-13. Frontend runtime change; model revision remains 93.

## Context

Nested module-import discovery walks every AST node below top-level functions
and classes. Most visited nodes are expression payloads, which cannot contain
`Import` or `ImportFrom` statements in the running interpreter's Python grammar.
A synthetic function with 500 call expressions makes the previous discovery
traverse 1,503 expression nodes to find one nested import.

## Decision

Keep the same top-level definition roots, then traverse only statements and
the structural `ExceptHandler` and `match_case` containers in breadth-first order.
Keep these containers at their original depth instead of flattening their bodies:
the existing discovery uses the last matching alias in BFS order, which can differ
from lexical order. Skip expression descendants, arguments, patterns and import
aliases; their containing statements already carry the import facts.

Import resolution, relative names, alias precedence and source scope are unchanged.
No persistent cache, parser change, dependency, target execution, report schema or
semantic capability is introduced. MODEL_REVISION stays 93.

## Verification

An independent work-bound test requires zero expression visits for the synthetic
payload while finding its import. It fails on the previous code (1,503 visits)
and passes after the change (zero). Other tests exercise handler/case BFS depth,
nested class/function scopes, asynchronous statement containers, try/except/else/
finally, and the unchanged exclusion of definitions under top-level conditionals.

Corpus and reviewed development reports must remain byte-identical, including
injection identities and outcomes. Measure fresh-process time and OS peak RSS
before accepting a performance claim. The existing instrumented profile locates
the work but cannot establish an uninstrumented speed gain.
