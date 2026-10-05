# ADR-0031: Bound opened inputs and reject ambiguous saved JSON

**Status:** Accepted, 2026-10-05.

## Context

Several metadata readers checked file size before an unbounded read. A stale size or a file
growing between the operations defeated the limit. Python's JSON parser accepted duplicate keys,
NaN, Infinity, and floats overflowing to infinity in saved reports. Deep JSON and TOML or an
unrepresentable JSON integer escaped reader diagnostics. A non-table `tool` in pytest configuration
raised `AttributeError`.

## Decision

All report, configuration, entry-point, target-version, deployment, pytest, and case-manifest
readers use one bounded byte reader. It consumes at most the allowance plus one byte from the
opened stream, accepts short reads, closes the stream on failure, and uses small chunks. Existing
limits and each reader's existing malformed-input policy remain in force. Deployment text retains
universal newline normalization.

Saved JSON rejects duplicate object keys at every level and non-finite numbers, including exponent
overflow. Parser recursion exhaustion and integer conversion failures become `ArtifactError`.
TOML recursion exhaustion follows the corresponding reader's malformed-input policy. Pytest
configuration validates the `tool` table before inspecting it.

This changes the accepted saved-artifact input contract, but introduces no schema, dependency,
framework model, execution, or source-universe expansion. Valid generated reports and baseline
fingerprints are unchanged. `MODEL_REVISION` remains `python-fastapi-dishka/22`.

## Consequences

Malformed saved reports receive an error instead of silently selecting one of conflicting values
or crashing. Oversized metadata cannot bypass the byte limit using stale file size information.
Regression tests cover stale size, exact byte boundaries, short reads, stream closure, UTF-8,
duplicate keys, number overflow, parser recursion, and malformed pytest tables. The semantic
corpus expectations remain unchanged.
