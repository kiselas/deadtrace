# ADR-0110: Visit each expression once per module-flow query

**Status:** Accepted, 2026-10-13. Runtime change; model revision remains 92.

## Context

ADR-0109 terminates alias cycles by remembering expressions along each recursive path.
Multiple assignments to a local can create a diamond-shaped search graph. Each path then
revisits the same descendants. A synthetic development example with two assignments per level
needs 47, 767 and 12,287 name checks at depths 4, 8 and 12 to reject module flow. The input is
AST data; the target is not executed.

## Decision

Search the same assignment relation with a query-local worklist and a set of expression
identities visited anywhere in that query. Each expression is expanded once. The predicates
that recognize module tables, loader calls, typed module parameters and imports are unchanged.
No cache survives the query. No source-universe, trust boundary, dependency, schema or
capability change is introduced.

The query is an existence test on a fixed graph: it returns true if any reachable expression
provides module-flow evidence. Revisiting an already expanded expression adds no new reachable
vertices. An iterative traversal preserves that answer while avoiding both alias-path
enumeration and recursive traversal depth. It supersedes only the algorithm of ADR-0109.

## Consequences

The same negative development examples need 10, 18 and 26 name checks. Positive module-table
examples still return true. The 178 existing corpus cases produce byte-identical default and
world-members JSON reports before and after (356 comparisons on identical input paths).
Field comparison must likewise retain identical reports, NEW 0 / LOST 0 and injection identities.

MODEL_REVISION stays `python-fastapi-dishka/92`. Performance and unchanged behavior are
evaluated separately from the semantic improvements in ADR-0108 and ADR-0109.
