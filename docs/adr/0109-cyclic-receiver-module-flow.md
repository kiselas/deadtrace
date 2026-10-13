# ADR-0109: Terminate cyclic receiver module-flow queries

**Status:** Accepted, 2026-10-13; model revision 92.

## Context

ADR-0107 uses the module-flow query for optional getattr values. The query follows local
assignments to distinguish ordinary unknown values from values that may be modules.
Assignments such as `receiver = receiver.target` or two mutually assigned aliases revisit an
expression indefinitely. Development-package recall injections exposed a RecursionError
before the candidate could complete its measurement.

## Decision

Each recursive module-flow query carries the identities of AST expressions already visited
on that path. Revisiting one returns no new module-flow evidence for that path. The caller
continues checking the name's other assignments and existing imports and parameter annotations.
The visited set is local to a query path, not shared across queries or alternative assignments.

## Consequences

`corpus/python/getattr_cyclic_receiver_aliases` raises RecursionError on revision 91 and
terminates on revision 92. Its ordinary receiver dispatches only the named method; an unused
method stays a candidate. The separate case `corpus/python/getattr_cyclic_module_receiver`
checks that a cyclic receiver with a sys.modules assignment keeps the possible module's public
definition protected. Its conservative guard is isolated from the unused-method control.
Target code is never imported or executed.

This bounds cyclic alias traversal, not arbitrary depth of acyclic expressions. The static
module-flow approximations remain conservative as before on the existing corpus.

MODEL_REVISION becomes `python-fastapi-dishka/92`; paired field runs and seed-7 injections
check the effect and any lost candidates before the revision is considered measured.
