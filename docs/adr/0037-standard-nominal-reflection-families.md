# ADR-0037: Standard nominal families refine external reflection

**Status:** Accepted, 2026-10-05. Refines ADR-0036 for supported standard nominal types.

## Context

Model 25 fixed the ADR-0035 unsafe finding, but guarding every project class member caused a large
injection-recall regression on Rich. Pydantic's overall injection result remained zero: localized
guard targets can reach other methods whose unknown reflection opens the whole graph. Fieldkit
recorded these clean-commit runs before refining the model. No holdout finding informed this change.

The initial receiver-provenance milestone is complete. This sequential, bounded refinement is the
one active semantic milestone. Its source-backed type summaries apply to Python 3.12, not to a
package-specific exclusion list. Primary sources are the
[pathlib hierarchy](https://docs.python.org/3.12/library/pathlib.html),
[LogRecord API](https://docs.python.org/3.12/library/logging.html#logrecord-objects) and
[CPython logging classes](https://github.com/python/cpython/blob/3.12/Lib/logging/__init__.py).

## Decision

1. Carry the explicit imported nominal origin alongside external annotation provenance. Equal
   origins survive joins; different or untyped external origins lose the nominal refinement. The
   annotation contract and unknown-write fallbacks of ADR-0036 remain unchanged.
2. Ship small standard nominal-family summaries for pathlib's concrete/pure path classes and
   logging.LogRecord. Related path classes are deliberately over-approximated as one family. Root
   builtins, selected standard exception roots, typing/ABC/enum mixins, and the listed logging
   classes have explicit non-overlapping ancestry relative to these families. These are semantic
   data; the scanner imports no target package and reads no external dependency sources.
3. For a supported origin, protect project members belonging to a possible subclass, together with
   members inherited from its project MRO. Any opaque external base remains possible, including a
   base reached through project ancestors. Computed bases, non-class resolved bases, conditional
   import alternatives, rebinding and local shadows retain protection. Test stand-ins are included
   even without nominal inheritance. Unrecognized annotation origins retain model 25's broader set.
4. Build a module binding-write index once per frontend instance. It includes nested writes
   conservatively, avoiding repeated AST traversal while classifying reflection targets. This is a
   transient source-derived semantic index, not a persistent result cache. Bare builtin spellings
   and imported/qualified standard names cannot justify exclusion after a relevant source write.
5. Do not filter method names or infer immutable dictionaries. Attribute aliases keep all members
   of possible receiver classes protected. Existing escaped references protect functions/classes
   handed to or attached to instances. Unknown external ancestry may still cause a guard to reach
   an unrelated broad boundary; this remains visible rather than being suppressed to raise a score.

`MODEL_REVISION` becomes `python-fastapi-dishka/26`. No report schema, config, dependency or source
universe change is introduced. Neither nominal metadata nor annotations enforce runtime types.
Dynamic class-base mutation, unseen callbacks and arbitrary untyped callers remain outside this
refinement's claim; future support requires independent safety cases.

## Consequences

The `nominal_external_reflection` corpus case keeps a Path subclass and an opaque-base subclass
protected, while leaving a plain unrelated method as a candidate. Model 25 protects that control;
model 26 passes. Existing external-reflection cases retain their independent expectations.
Tests additionally cover rebinding, conditional bases, builtin shadows, computed bases, project
mixins, standard roots and nominal joins. Full gates and clean-commit field measurements are
recorded in the accompanying results document. No market-quality or package-recall improvement is
claimed merely from more precise boundary targets.
