# ADR-0033: Join receiver types across branches and loop back edges

**Status:** Accepted, 2026-10-05.

## Context

ADR-0032 pinned complete-world false findings for receiver assignments in branch alternatives
and loop back edges. The single last-seen type could omit a method that actually executes.
The user approved starting a receiver-flow semantic milestone on 2026-10-05. This replaces the
previous inventory-only working milestone for this bounded change; it does not authorize other
framework models or trust-boundary expansion.

## Decision

1. A local receiver value contains a finite set of possible project class names, an explicit
   unknown flag, and an external-value flag. Branches start from the same entry state; their
   exit states are joined. An absent binding on one path contributes unknown. Conditional
   expressions and local aliases preserve alternatives. Straight-line assignments overwrite
   previous values, and their right-hand sides execute before updating the binding.
2. Known receiver alternatives resolve to each possible member, preserving inherited-member
   lookup and subclass dispatch. Unknown alternatives retain existing name-scoped protection;
   they never select the last known class as the only receiver. Dynamic attribute lookup on
   project-only receiver sets protects the union of those classes' members. Instances escaping
   to an unknown consumer expose all their possible project classes.
3. For/async-for and while bodies are revisited with the joined entry/back-edge state until
   stable. Zero-iteration and break paths are included. Limits are 32 iterations per loop and
   256 passes shared by a scope. Exhaustion adds unknown to all current receiver values and
   revisits the body under that widened state; it does not discard alternatives. It may reduce
   recall, never justify a stronger negative finding.
4. Exception paths conservatively join try prefixes and invalidate names written in nested
   statements before handlers/finally. Match captures, loop targets, destructuring, deletion,
   augmented assignments and opaque context-manager yields cannot retain stale inferred types.
   Container identity is retained at a join only when present on all paths. Dynamic-module
   provenance is joined conservatively.
5. Return, raise, break and continue do not prune later syntax or create a full control-flow
   graph in this milestone. Their paths are over-approximated. Heap fields, unannotated factory
   returns, interprocedural value sets, arbitrary expression effects and annotation-policy
   soundness are not newly claimed as fully modeled. The existing annotation assumptions remain.

The value/join domain is in `receiver_flow.py`; structured traversal stays in the Python frontend.
Targets are still read and parsed only. There are no new dependencies, runtime execution,
source-universe expansion, report schemas, or diagnostic codes.
`MODEL_REVISION` becomes `python-fastapi-dishka/23`; reports from model 22 are method-incomparable.

## Consequences

Both ADR-0032 violations are fixed and move to `corpus/python/`, with the same independent target
expectations. Their unused controls remain findings. Tests additionally exercise branch-order
invariance, aliases, conditional expressions, straight-line overwrites, RHS ordering, loop entry
and back edges, unknown writes, exception prefixes, escapes, localized reflection and widening.
Scope budgets bound repeated traversal rather than introducing a cache or executing a target.

The next priority is finite string-name propagation for the Pydantic dispatch case described in
the quality research. It is not silently added here: narrowing that guard can create many new
findings and requires its own safety case and independent review.

Both promoted cases were validated against the archived `0d28568` source (model 22): each fails
with its reachable method failing `not_candidate`. Model 23 passes them and their independent
unused controls. Local verification: Ruff check/format, Windows and Linux-target mypy,
379 passing tests with 93.00% branch coverage, both case validators (114 corpus cases,
403 targets), offline isolated build and outside-checkout wheel smoke. Two skips are Windows
symlink privileges and the empty known-violation parameter set. Runtime Linux CI remains pending.
