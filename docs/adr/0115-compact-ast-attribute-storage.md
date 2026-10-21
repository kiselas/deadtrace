# ADR-0115: Share keys in AST attribute dictionaries

**Status:** Accepted, 2026-10-13. Storage change; model revision remains 93.
Storage superseded by ADR-0117 (slotted nodes), 2026-10-21.

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

## Measured tradeoff

Fresh-process comparisons on eight reviewed development inputs used CPython 3.12.4
on Windows, the same locked runtime and files, alternating control/candidate order
in two pairs per input. Control was `8770065`, candidate `8cd0a86`. All text and
JSON outputs matched byte-for-byte in both separate series, as did the 358 corpus
reports. The input and analyzer digests were checked between runs.

For two large FastAPI applications (599 and 738 files), median local paired RSS
ratios were 0.797 and 0.814: about 20.3% and 18.6% less peak memory. Their time
ratios were 1.046 and 1.040. Pydantic 2.13.5 used about 14.9% less peak memory
with a time ratio of 1.047. Across all eight text comparisons, time ratios ranged
from 0.949 to 1.078. The smallest input used about 0.5 MiB more peak memory.

Accept the lower retained memory on large inputs at this modest scan-time cost.
This is a memory tradeoff, not a general speed improvement or evidence of resource
superiority over another analyzer. Two pairs do not establish small timing effects
as stable. Subsequent frontend work should remove the additional runtime cost.
