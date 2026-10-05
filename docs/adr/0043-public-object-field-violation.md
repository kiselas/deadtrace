# ADR-0043: Public API objects expose methods through their public fields

**Status:** Accepted, 2026-10-05; violation recording, model 29 unchanged.

## Context and decision

ADR-0042 is complete. Audit of the inherited development verdicts found two Pluggy false findings:
TagTracer.setwriter and setprocessor, available to external clients through PluginManager.trace.root.
The library root policy expands exported classes and their public methods but stops at public
instance fields. A source-local chain with known project field types is therefore overlooked.

The independent public_object_fields case pins this present safety violation before implementation:
the exported Manager exposes trace.root.setwriter, while Trace._unused is an unrelated private
control. The one active semantic milestone is carrying the existing inferred project field types
into automatic library/package-export API closure. Local inspection-tuple aliases are deferred:
correcting confirmed real-package false findings is a higher priority than another micro-pattern
with no measured package gain.

The fix must retain public methods reached through public fields and project inheritance, terminate
on cycles, keep explicit script/application worlds local, and record its API-root capability change.
No package-specific name rule, target execution, external dependency reader or public schema change
is introduced. General function-return/container provenance is outside this bounded milestone.
