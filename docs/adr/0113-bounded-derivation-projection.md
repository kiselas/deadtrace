# ADR-0113: Project only the shown derivation prefix

**Status:** Accepted, 2026-10-13. Report runtime change; model revision remains 93.

## Context

The JSON report displays at most 2,000 derivations, but the projection built dictionaries
for every derivation and sorted them all before slicing. Large multi-world analyses therefore
allocated many temporary dictionaries that never appeared in the report.

## Decision

Count derivations from the existing world tuples. Use `heapq.nsmallest` to select the same
stable prefix of raw Derivation objects, using the existing world, target display name,
reachability and edge-kind sort key. Convert only selected objects to dictionaries.
For equal keys, preserve input order exactly as the previous stable full sort did.

The graph, solver, finding explanations, schema and 2,000-item limit are unchanged.
There is no persistent cache or dependency beyond the standard library. MODEL_REVISION
stays `python-fastapi-dishka/93`; default and world-members report bytes must be identical.

## Verification and scope

An independent projection test includes shuffled derivations and equal keys with different
details. It compares the result with a stable full-sort reference, checks total/truncated,
and limits dictionary conversion to the displayed prefix. With a limit of three and 53
derivations, the previous implementation converts 53; this implementation converts three.
Empty and untruncated prefixes are also checked. The test fails on the previous code.

Temporary derivation dictionaries are bounded by the display limit, not the total count.
This does not bound memory used by the analysis graph, world-member output or other report
sections. Measure any elapsed-time or process-RSS effect separately on identical inputs;
the default text comparison with Vulture cannot establish this JSON-specific effect.
