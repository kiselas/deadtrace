# ADR-0047: Record direct guard coverage alongside inherited upstream attribution

**Status:** Accepted, 2026-10-05. Diagnostic work; scanner model 31 unchanged.

The user selected measured, broadly useful consumer summaries as the next improvement direction,
and requested immediate attribution before further hypotheses. The inherited held_by field records
the first conservative transition on a selected derivation and cannot identify all direct guards.

Add direct_guards to newly produced private field facts and injection ledger rows. For each world,
include global/world-local boundaries whose source is reached and whose explicit target or
whole-graph coverage includes the definition; respect class/module gates and reached deserializers
that open them. Record world, source, domain, reason, location, whole-graph shape and gate state.
Coverage is not a unique cause or proof that this boundary won the solver's selected derivation.
Resolved targets can also have guard coverage. Keep held_by unchanged, and leave historical rows
untouched. Missing attribution in older worker facts is null, distinct from an empty computed list.
The optional direct_guard_schema=1 marks new facts; public scanner report/config schemas are unchanged.

Extend the private replay diagnostic with exact-consumer cuts of escaped_class boundaries,
including combined cuts, so a proposed consumer rule's upper bound does not remove unrelated
escape boundaries at the same source. Budget exhaustion remains explicit and cannot establish gains.

No target execution, dependency/source-universe expansion or detector semantic change is introduced.
The next semantic milestone must be selected by dev-only replay measurements and independently
pinned controls. Pydantic receiver-origin infrastructure, external hook tables and fresh holdout
tuning are deferred. Fresh blind precision evaluation follows two or three completed semantic steps.
