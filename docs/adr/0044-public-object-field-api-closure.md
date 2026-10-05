# ADR-0044: Automatic public API discovery follows source-known public fields

**Status:** Accepted, 2026-10-05. Resolves ADR-0043; model revision 30.

## Decision

Share the existing source-inferred class-field type map with automatic library and package-export
discovery through the internal PythonProgram record. A public API class exposes the public API of
project objects obtainable from its public fields. Add those project classes to the existing API
worklist; expand their public methods/nested classes and public fields recursively. Also follow
project inheritance so inherited public methods and field contracts are available. Existing
deduplication of roots terminates cycles. Build a source-local field/base adjacency once per
automatic world discovery; no persistent cache is added.

Reuse existing frontend field inference, including constructor parameter types, project constructor
values and declared annotations. Its annotation contract supports a single project class, including
forward annotations and a transparent Final declaration. This change does not strengthen or narrow
that inference and does not assert unknown fields are empty. Private fields, private ordinary methods
and unrelated classes are not added to API roots by this rule. Existing implicit Python/metaclass
guards still apply. Explicit configured worlds are unchanged; automatic package-export worlds next
to framework applications receive the same closure as automatic library worlds.

The internal source-derived field map changes no public report/config schema. The
python.library-roots capability rises from 1 to 2; model revision becomes python-fastapi-dishka/30.
No dependency, target import/execution or external source-universe expansion is introduced.

## Evidence and limits

The independently pinned public_object_fields case moves to corpus with target expectations
unchanged. Controls cover private fields/methods, unrelated classes, explicit scripts, exports next
to an application, inherited fields/methods, cyclic fields and Final/quoted annotations. Required
gates and clean-commit field results are recorded after verification. The motivating Pluggy methods
are reachable through PluginManager.trace.root under this general rule; no Pluggy-specific names
or source paths are encoded.

General return/container flow, unions of possible field types, properties returning opaque values,
subclasses supplied only by unavailable consumers and serialization compatibility are not modeled
by this change. Packaging's old-pickle compatibility findings remain a separate evidence/contract
problem. The local inspection-tuple alias proposal is deferred; this public-field milestone is the
only active semantic change for the current cycle.
