# ADR-0035: External receiver provenance and reflected subclass methods

**Status:** Accepted, 2026-10-05, violation recording; implementation follows in this milestone.

## Context

The user approved the next bounded receiver-provenance milestone after ADR-0034. Pydantic's
`path_type(p: 'Path')` already classifies `p` as external, including its TYPE_CHECKING import.
Immediate dynamic getattr dispatch nevertheless opens a whole-project boundary. Stored getattr
values have the opposite problem: no guard for a method supplied by a project subclass.

Before changing semantics, `external_reflection_value` independently records that a Path parameter
may receive a project subclass; a retrieved and subsequently called `check` method may run.
Model 24 reports that method as a candidate. The unused private function is an independent control.
`tests/test_known_violations.py` pins exactly `_tool.py:ProjectPath.check`.

## Decision

Keep one active milestone: propagate explicit external annotation provenance across local receiver
joins and use it to localize reflection while retaining possible project subclass methods and test
stand-ins. Unknown origins keep broad protection. Annotations remain the existing analysis contract,
not runtime enforcement. Do not infer immutable keys from a mutable global dictionary, execute target
code or read dependency sources outside the scanner universe. Model 24 is unchanged in this recording.

## Consequences

The violation must be fixed before narrowing the immediate-call guard. This milestone requires its
own implementation ADR, raised model revision, negative cases, complete verification and package
evaluation. A fixed case moves to corpus with the same independently specified target expectations.
