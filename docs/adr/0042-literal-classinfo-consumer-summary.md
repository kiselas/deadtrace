# ADR-0042: Literal class-info tuples have an inspection consumer summary

**Status:** Accepted, 2026-10-05; model revision 29.

## Context

ADR-0041 is complete. The next single bounded milestone distinguishes the use of class values by
an inspecting builtin from their escape to an arbitrary consumer. Previously direct class arguments
to isinstance/issubclass already skipped ordinary-method exposure, but literal tuple elements were
visited as independent escaped references and expanded to every exposed method. General function
return/container provenance remains a later proposal; this milestone supplies one bounded consumer
summary without inferring the values of returned containers.

## Decision

For an unshadowed bare builtin isinstance or issubclass call with exactly two positional arguments,
no keywords, and literal tuple classinfo, inspect nested tuple elements. Resolved project class
references are accounted for as class targets of the existing conservative escaped-callable boundary
without treating their ordinary methods as callable callbacks. Preserve alternative definitions.
Unknown expressions, starred elements, calls, lists and unsupported class-info expressions continue
through ordinary traversal and retain escape protection. Earlier or separate escapes are unaffected.

Reject this refinement when module bindings/writes, local or enclosing function bindings, or any
star import can shadow the builtin. Index modules containing star imports once, including external
stars and conditional imports, as a transient source-derived fact. Do not infer builtin aliases or
parameter/return container contents. Existing implicit class/metaclass execution guards retain
custom inspection hooks and calls made from them; this change does not claim precise metaclass
execution analysis. An unknown consumer still exposes class methods.

The [Python 3.12 builtin documentation](https://docs.python.org/3.12/library/functions.html#isinstance)
specifies recursively nested class-info tuples. Metaclass hooks are part of
[customizing instance and subclass checks](https://docs.python.org/3.12/reference/datamodel.html#customizing-instance-and-subclass-checks).
The independent corpus case separates an inspection-only method from a class handed to an unknown
consumer. Scope/shadowing, nested tuples, unsupported expressions and metaclass-call controls are
tested. Required gates and clean-commit package results follow in the results document.

## Limits

This is a local consumer summary, not general interprocedural points-to analysis, immutable heap
inference, or a Pydantic descriptor/partial model. Builtin monkeypatching outside available source
remains outside the existing builtin contract. No target execution, external source reads, public
schema or dependency change is introduced. Revision 29 identifies the changed analysis semantics.
