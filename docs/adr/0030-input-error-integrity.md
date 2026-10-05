# ADR-0030: Input errors remain visible across inventory and metadata readers

**Status:** Accepted, 2026-10-01.

## Context

The repository audit reproduced several operational failures under CPython 3.12.4:

- `os.walk` silently ignored a denied root or child directory, so inventory could report success
  without reading all source. A reachable script next to the denied directory could produce a
  complete semantic report with a negative finding.
- Python encoding cookies naming non-text codecs (`base64_codec`, `hex_codec`) raised `LookupError`
  outside the source reader's diagnostic handling.
- Invalid UTF-8 in configuration or metadata escaped the TOML readers as `UnicodeDecodeError`.
- Configuration used an unbounded `tomllib.load`, despite the project input limit of 16 MiB.
- A version such as `fastapi===oops` or `version = "oops"` in a lock file raised `InvalidVersion`.

CI's wheel check ran only `--version`, which did not exercise these readers or saved artifacts.

## Decision

1. Directory traversal records failures as existing inventory issue `DT1001`. The same issues
   participate in both discovery passes and the whole-snapshot retry. Valid readable files remain
   in inventory. Existing analysis handling marks worlds partial and withholds negative findings.
2. Source reads and verification handle codec lookup failures as `DT1001`, just like decoding errors.
3. Configuration reads at most `MAX_ARTIFACT_BYTES + 1` bytes from the opened stream. Oversized data
   raises `ConfigurationError`; invalid UTF-8 follows the same error path as malformed TOML. The CLI
   exits 2. Entry-point and version readers apply their existing malformed-TOML policies to invalid
   UTF-8 (`DT4101` for entry points, unavailable metadata for dependency versions).
4. Valid version strings retain their existing normalized form. Invalid strings stay visible in
   dependency metadata. An imported modeled dependency with an invalid version gets the existing
   `DT4001` compatibility guard, so unknown compatibility cannot produce strong negative findings.
   An invalid version of an unmodeled dependency does not create a framework compatibility claim.
5. One portable wheel smoke script runs in CI on Windows and Linux. It checks that the package
   comes from outside the checkout, then exercises inventory, complete analysis, deterministic JSON,
   explain, baseline, compare, and input errors. A target contains a file-writing statement and a
   raising statement; neither may run, and source content and modification time must stay unchanged.

These fixes enforce existing input and compatibility contracts. They introduce no framework model,
schema, dependency, or source-universe expansion. `MODEL_REVISION` remains 22: valid-input behavior
is unchanged, and failures already participate in report comparability. The source discovery,
compatibility, and schema policies remain those of ADR-0007, ADR-0015, ADR-0018, and ADR-0021.

## Consequences

Previously silent directory failures now cause inventory/scan exit 2. Previously crashing codec and
configuration inputs receive diagnostics. An uninterpretable modeled dependency version yields a
partial world; `--require-complete` exits 2. Existing valid corpus expectations remain unchanged.

Regression tests cover root and child directory denial, preservation of readable definitions,
source encodings, UTF-8 metadata, both sides of the configuration size limit, and malformed versions
in both metadata formats. These are operational tests, not new semantic fixture expectations.

The complete verification results and remaining reader risks are recorded in
[the repository audit](../audit-2026-10-01.md). CI runs are still required to confirm the Linux
environment; local evidence is Windows only.
