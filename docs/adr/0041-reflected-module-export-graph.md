# ADR-0041: Follow reflected names through the project export graph

**Status:** Accepted, 2026-10-05. Resolves ADR-0040; model revision 28.

## Decision

Reflected project-module values retain callable definitions exposed through imports, not only
definitions lexically owned by that module. For finite names, first select the module's exported
name, then follow its import binding to the destination name; never compare that alias to the
destination definition's original name. Unknown names retain all imported callable alternatives.
Existing affix selection on directly owned definitions remains unchanged.

Traverse source-universe module bindings iteratively, including each conditional import binding
and star re-export. Preserve all direct definitions with a selected name. A visited set keyed by
module and selected names terminates cycles; traversal is bounded by the finite source export graph
and does not rely on the resolver's two-pass name hints. Imported modules themselves are not
callable targets; opaque external imports retain the previous policy. No dependency is imported
or read outside the universe. No persistent cache or new public schema is introduced.

The reflected-value boundary remains conservative and localized. Immediate nested getattr calls
keep their existing broader dispatch fallback; narrowing them would be a distinct milestone.
The implementation does not infer assignments to module attributes, arbitrary heap aliases,
module subclasses, or external dynamic namespaces. Those existing limitations are not claimed fixed.

## Evidence

The independently pinned imported-alias case moves to corpus unchanged. Tests cover literal and
unknown names, a renamed multi-module chain, conditional alternatives, star re-exports, cycles,
and a chain longer than the existing resolver hints. Unreferenced control functions remain
unreached. ADR-0039 is complete; this is the only active semantic milestone. Required gates and
clean-commit field measurements are recorded in the results document. Dependencies, report/config
schemas and scanner trust boundaries remain unchanged.
