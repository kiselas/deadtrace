# ADR-0036: Localize reflection on externally annotated values

**Status:** Accepted, 2026-10-05. Resolves ADR-0035.

## Context

ADR-0035 independently pinned a callable obtained from a Path parameter: a project subclass's
method was reported even though it may run. The same receiver used in an immediate getattr call
instead protected the whole graph. Pydantic's `path_type` illustrates the latter: its Path annotation
already resolves through a TYPE_CHECKING import, so missing import information is not the cause.

The user authorized starting this bounded milestone. It completes ADR-0034 and is the sole semantic
milestone for this cycle. There is no need to pretend a mutable name dictionary has constant keys.

## Decision

1. Add an external-annotation provenance flag to receiver values. A simple imported external type
   may establish it under the existing annotation contract (ADR-0008). String annotations are parsed
   statically. Typing/typing_extensions names, module types, generics, unions and inconsistent import
   alternatives do not establish this narrower origin. No target or dependency code is executed.
2. Aliases and structured receiver joins propagate provenance. Joining an untyped external origin
   loses it. Unknown or project alternatives prohibit narrowing. Existing receiver invalidations,
   exceptions and loop widening preserve conservative fallback. Imports and newly bound definitions
   forget the flag. Scopes containing walrus, comprehensions, global or nonlocal declarations do not
   use this refinement until their expression/closure writes are modeled more precisely.
3. An externally annotated instance can supply **any project class member** through reflection.
   Protect all such members, including subclasses, indirect external-base inheritance, structural
   stand-ins and test doubles. Do not match external ancestry or filter these targets by method name:
   dependency inheritance and attribute aliases are not fully known. This is deliberately broader
   than assuming that a Path parameter can only invoke pathlib methods.
4. Apply the same localized boundary to an immediate call and to a stored reflected value, including
   a literal-name getattr value. Empty selections emit no boundary, because an empty-target boundary
   would open the entire graph. Project functions or classes assigned/passed as attribute values keep
   the existing escaped-reference/callable protection. Unknown origins retain existing handling; an
   untyped external factory result cannot justify this refinement.
5. Annotations remain an **analysis input contract**, not runtime enforcement or proof against arbitrary
   untyped callers, dynamic monkeypatching or callbacks returned by unseen code. This milestone does
   not claim full soundness for those cases, arbitrary stored getattr values, module reflection or
   annotation shadowing. It does not add dictionary propagation or external dependency inspection.

`MODEL_REVISION` becomes `python-fastapi-dishka/25`. No dependency, source-universe, report schema,
diagnostic code or config change is introduced. Existing target execution prohibitions remain.

## Consequences

The pinned reflected-value case moves to corpus with its independent expectations unchanged.
A second independent case mutates the name dictionary, uses a receiver alias and a TYPE_CHECKING
string annotation: subclass methods may run, but an unreferenced module function remains a candidate.
Against archived model 24 (`49a015b`), the first fails exactly for `ProjectPath.check`, the second for
`_unused_control`. Model 25 passes both. Additional tests cover stored/direct/literal lookup, aliases,
external bridge inheritance, plain and test stand-ins, escaping functions and unknown-write fallback.

The broad method guard intentionally remains. This can improve module-function recall while retaining
many dead methods. Full verification and clean-commit package measurements belong in the associated
results document; injection recall and inherited field labels do not establish market-leading quality.
