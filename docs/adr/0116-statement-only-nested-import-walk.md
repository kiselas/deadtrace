# ADR-0116: Visit statement containers when finding nested module imports

**Status:** Accepted, 2026-10-13. Frontend runtime change; model revision remains 93.

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

## Evaluation and acceptance

The 358 default/world-members corpus reports remain byte-identical. On eight
reviewed modern-stack development inputs, text and JSON reports matched in all
paired repetitions. Exact seed-7 injection identities and outcomes stayed at
534/721 development and 964/1565 holdout. Model 93 remains unchanged.

Four alternating fresh-process pairs on one large FastAPI input against the
compact-storage parent gave a median local time ratio of 0.902 and RSS ratio
0.9994. Individual time ratios ranged from 0.661 to 1.066, so this is an observed
sample result, not a stable general speed claim. Separate four-pair comparisons
against that parent gave time ratios 0.951 on FastAPI and 0.987 on Dishka.

Combined storage/traversal comparisons against the earlier parent retained the
19–20% text RSS reduction on two large FastAPI applications, with time ratios
1.010 and 1.015 in the two-pair series. A 44.5% slowdown on the FastAPI package
in one text series did not reproduce in JSON or a four-pair text repeat; the
repeat against the earlier parent gave time ratios 1.031 for FastAPI and 0.997
for Dishka. Preserve the anomalous run rather than replacing it with the repeat.

Accept elimination of unnecessary expression traversal with unchanged findings
and the measured memory benefit retained. Timing variance remains substantial;
these measurements do not establish resource superiority over another analyzer.
