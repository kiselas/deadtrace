# ADR-0115: Share keys in AST attribute dictionaries

**Status:** Proposed, 2026-10-13. Storage change; model revision remains 93.

## Context

A diagnostic memory profile of a large FastAPI application with 599 source files
at model 93 attributed about 344 MiB of live traced allocation to parsing, versus
about 24 MiB of source text. Full-project ASTs are retained by the analysis model.
Changing only solver storage would leave the largest allocation group untouched.

In a synthetic source with 10,000 repeated functions, the dictionaries of nodes
with attributes occupied 22,800,184 bytes on CPython 3.12. Transferring their
attributes through ordinary Python instances reduced that group to 10,160,296
bytes in about 0.1 seconds. Complete AST dumps, including locations, matched.
These object-size figures diagnose storage; they are not process RSS benchmarks.

## Decision

After standard-library parsing and before constructing the shared `ParsedSource`,
replace nonempty node dictionaries with dictionaries populated on temporary
ordinary instances. One holder class per standard-library AST node type belongs
to the running interpreter's fixed grammar. Classes can share keys across files
and analyses, but retain no node values, source strings, or project objects.
CPython can share keys among instances of the same holder class. The dictionary
remains a normal, independently mutable dictionary after the holder is released.
Seed the first attribute before the bulk dictionary update: updating an empty
holder dictionary alone can replace the shared layout with an ordinary full copy.
Walk child fields with a local worklist; no recursive conversion is needed.

Keep the original AST node identities, exact types, attribute insertion order,
and every attribute value, including location integers, child nodes and lists.
No AST subclasses, new parser, dependency, persistent project cache, target execution,
source-universe change, schema change or semantic capability is introduced.
Analysis passes still must not mutate the published `ParsedSource`.

## Verification and consequences

Independent tests compare all node identities and attribute value identities,
complete dumps, deepcopy and pickle round trips, Unicode source segments, and
separate parses and collection of parsed nodes after their result is released.
The holder table is bounded by the interpreter grammar, not the input. A CPython
storage-budget test on 1,000 repeated functions must
reduce aggregate dictionary storage by at least 35% without changing the AST.

Existing corpus and reviewed development reports must remain byte-identical;
injection identities and outcomes must remain unchanged. Fresh-process paired
measurements must include the additional traversal and dictionary copying, and
measure both time and OS peak RSS. No overall speed or memory claim follows
from the synthetic dictionary budget alone. Model revision stays 93.
