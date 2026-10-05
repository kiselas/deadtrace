# ADR-0034: Finite immutable local names for known-receiver dispatch

**Status:** Accepted, 2026-10-05.

## Context

The user approved continuing the finite-name milestone after ADR-0033. A computed attribute name
currently protects every method of a known receiver even when local assignments restrict that name
to two literal strings. Narrowing this guard needs positive value evidence and unknown-write controls.

The motivating Pydantic `path_types` example is more difficult: its module-level dictionary is
mutable, and its receiver is opaque. A literal dictionary initializer does not prove runtime keys.
An opaque object's attribute may hold a callable whose definition has an entirely different name.
Filtering all project definitions by their original names would therefore be unsafe.

## Decision

1. Add an immutable string domain to the existing structured local-flow state. A value is either
   at most 32 possible strings or explicitly unknown. Literal strings, local aliases, conditional
   expressions, assignments and annotated assignments contribute values. Branches and loop back
   edges join them. Missing bindings, unknown writes and excessive alternatives yield unknown.
2. Receiver-state invalidations also invalidate string values: opaque loop/context targets,
   destructuring, match captures, deletion, augmented assignment, imports and new definitions cannot
   retain a previous finite string set. Exception-prefix invalidation and exhausted loop budgets
   retain conservative protection. Scopes containing walrus expressions, comprehensions, global or
   nonlocal declarations do not propagate local string sets in this milestone; their expression or
   closure semantics need separate modeling. Direct string literals can still be inspected.
3. Finite names filter the existing known-receiver member set, including inherited members and
   overrides. Empty finite selections do not create an empty-target boundary: such a boundary means
   whole-graph protection, not an empty selection. Unknown receivers keep the existing broad guard,
   even with finite names. Unknown names retain existing conservative handling.
4. Do not infer dictionary keys, heap values, iteration contents, factory returns or global constants
   from declarations. Do not add package-specific exceptions. Existing affix matching and receiver
   modeling assumptions are unchanged; this is not a proof of arbitrary reflection or monkeypatching.

`MODEL_REVISION` becomes `python-fastapi-dishka/24`. Target code remains read and parsed only. No
dependencies, runtime execution, report/config schemas or source-universe expansion are added.
ADR-0033 is completed; this is the sole active semantic milestone for the current cycle.

## Consequences

The independent `finite_dispatch_names` corpus case protects both selected methods, keeps an
unselected method as a candidate and protects both methods of a second receiver after an unknown
write. Against archived model 23 (`d45d708`), validation fails because `First.unused` is protected;
model 24 passes. Additional tests cover aliases, overwrites, branch/loop joins, invalidations,
closure/comprehension fallback, mutable dictionaries, empty selections, opaque receivers and the
32-name bound. The Pydantic broad guard remains: its removal requires a separate justified model.

Package evaluation and full verification are recorded in the associated results document after
running the gates on this implementation. This change alone does not establish market-level quality.
