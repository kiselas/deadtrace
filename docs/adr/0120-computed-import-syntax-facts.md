# ADR-0120: Share frontend syntax facts and visitor dispatch metadata

**Status:** Proposed, 2026-10-14. Runtime only; no semantic revision bump.

## Context

ADR-0118 collects star imports, nominal stores and scope constructs in one module
walk. Queries for computed-module imports and their possible name prefixes still
walk the same trees separately. An owned function containing 500 calls is visited
three times across resolver initialization and repeated import/scope projections.
It needs one traversal for these set/boolean-valued facts, not three.

The execution visitor also constructs 16 bound callbacks on every `_visit_nodes`
invocation, even for an empty iterable or nodes with no handler. Those mappings
have the same grammar keys and method names for every invocation.

## Decision under evaluation

Collect both computed-import projections in the existing module syntax walk.
Keep only their immutable prefix union and project boolean on the resolver. They
retain no source objects through a global cache. Filter candidate call shapes
before constructing dotted names: only the existing import functions and the
existing `modules.get` forms can contribute. Empty-field grammar leaves, such as
operators and contexts, cannot contain facts and are not pushed onto the worklist.

Preserve both existing projections separately. Literal string arguments/keys do
not count as computed; missing/non-string arguments do. `modules[__name__]` gives
the current module prefix. Relative prefixes from import calls normalize to the
empty prefix; subscript prefixes retain their existing spelling. The raw-source
`import`/`modules` prefilter applies only to prefix discovery, not the project flag;
normalized Unicode identifiers can therefore set the flag without a prefix. This
change does not redefine those policies or add new aliases/call forms.

Store dispatch method names in one read-only grammar-keyed mapping, and bind only
the selected callback after the existing handled-node check. Keep visitor order,
subclass overrides and exact-type selection. The mapping contains standard-library
classes and constant strings, never bound methods or visitor/project objects.
Do not cache bound callbacks on a visitor: that would create a self-reference cycle.

Computed import facts become eager during resolver initialization. Small inputs
that never queried them may pay extra work, so traversal reduction is not by itself
a speed claim. No target execution/import, parser, source-universe, dependency,
framework rule, schema or semantic revision change is introduced. ASTs stay immutable.

## Verification and acceptance

An independent work-bound test fails on the parent with three visits to a 500-call
payload; the candidate requires one across repeated queries and skips empty-field
leaves. Twenty-one owned boundary cases preserve literals, prefixes, relative
names, current-module keys, package/call lookalikes, zero arguments and Unicode
normalization. Existing scope/store/star-import tests remain unchanged.

Independent dispatch bounds fail before this change: two empty/unhandled visits
bind 32 callbacks rather than zero; a mixed input binds all 16 rather than its two
selected callbacks. Tests also preserve callback order, handled-node skipping,
overrides and immediate visitor collection after release without a GC cycle.

The initial prototype matched all syntax projections on 549 static source/corpus/
fixture files. The production implementation, including empty-leaf pruning, also
matched normalized facts from the trusted `437c252` source snapshot on all 549 files.
This is a static-data equivalence check, not execution of target code or a field
measurement. No speed or memory claim follows from it.

Before accepting, rebase onto the accepted semantic parent, run every quality/build/
wheel gate, compare all fixed default/world-members corpus bytes, reviewed modern-
stack text/JSON bytes and exact seed-7 injection outcomes. Measure alternating
fresh-process time and OS peak RSS only when no competing local checks/scans run.
Record all results and any regressions; model revision stays at the semantic parent.
