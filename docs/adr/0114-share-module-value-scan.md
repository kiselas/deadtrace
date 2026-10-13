# ADR-0114: Share the module-value scan within one resolver

**Status:** Accepted, 2026-10-13. Frontend runtime change; model revision remains 93.

## Context

A diagnostic profile of a large FastAPI application found two full project walks in
`_modules_held_as_values`: one for named member dispatch and one for the gated member
universe. Together they took about 18 cumulative seconds in an instrumented run.
That profile identifies repeated work; its absolute time is not an uninstrumented benchmark.

## Decision

Keep one immutable set of directly held module names on the resolver, which belongs to
one analysis of a fixed module/symbol snapshot. Both projections reuse it. Named dispatch
copies the set before adding computed-import prefixes, because those prefixes are not part
of the directly held module universe. An empty set is cached as well. No state survives
the resolver or is shared between analyses. No persistent cache, new dependency, source
universe change, trust boundary or report schema is introduced.

## Verification and consequences

A synthetic module-table case includes a nested import and a computed import prefix.
The named projection includes both direct and prefix-only modules; the gated universe
includes only the directly held one. The two projections together must walk each module
once. The previous code walks four modules eight times; the new code walks them four times.
The independent work-bound test fails on the previous implementation.

MODEL_REVISION remains `python-fastapi-dishka/93`. Existing default/world-members JSON
reports and field findings must remain byte-identical. Repeat uninstrumented paired
measurements before claiming speed or peak-RSS improvement. The retained set contains
only module-name references and is bounded by the current source universe.
