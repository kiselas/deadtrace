# ADR-0032: Pin independently demonstrated receiver flow violations

**Status:** Accepted, 2026-10-05.

## Context

Quality research exposed two complete-world safety violations in model 22: a receiver assigned
different classes on branch alternatives loses the first class at a subsequent method call; a
receiver reassigned in a loop loses the later class at the call on the next iteration.

## Decision

Apply ADR-0006. Record both cases in `fixtures/known-violations/` with independent `not_candidate`
expectations for both reachable methods and a `candidate` unused control. Pin exactly the unmet
targets in `tests/test_known_violations.py`. No analyzer behavior changes in this decision.

These are current violations, not promises of future supported semantics. A correct fix may
resolve both receivers or protect them locally; it must not suppress the entire world. The active
inventory-only milestone is unchanged. `MODEL_REVISION` remains 22.

## Consequences

The suite now prevents silent changes to these unsafe outcomes, while showing explicitly that
they remain unfixed. A future receiver-flow milestone must remove the pinned violations, add its
model ADR and revision, and move passing cases into the corpus. The ordered research plan is in
[the quality audit](../quality-research-2026-10-05.md).
