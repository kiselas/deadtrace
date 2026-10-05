# Finite local dispatch names: results, 2026-10-05

Model 24, implementation commit `300dad7`, follows immutable local string alternatives when
filtering dynamic lookup on known project receivers. It includes assignment order, aliases,
branch joins, loop back edges and unknown-write fallback. See
[ADR-0034](adr/0034-finite-local-dispatch-names.md) for its deliberately bounded scope.

## Independent checks

The new corpus case has five independently specified lexical targets. `First.run` and
`First.other` may execute; `First.unused` has no caller. Both methods of a second receiver remain
protected when a branch supplies an unknown name. Against archived model 23 (`d45d708`), the
validator fails because there are no findings; a separate static analysis confirms the unused
control is absent. Model 24 passes without changing those expectations or executing the target.

Added 29 tests covering finite assignments, aliases, branch/loop joins, unknown writes,
imports/decorated redefinitions, exceptions, closure/comprehension fallback, mutable containers,
empty selections, opaque receivers and domain widening. Full local verification passed:

- Ruff check and format; mypy for Windows and the Linux target.
- 408 tests passed, two skipped, 93.08% branch coverage. Skips concern Windows symlink privileges
  and the empty known-violation parameter set.
- Seed validator: 6 cases, 12 targets. Corpus: 115 cases, 408 targets, 115 semantic cases.
- Offline isolated source/wheel build and wheel smoke outside the checkout, including determinism,
  saved artifacts, input errors and the target-execution sentinel. Runtime Linux CI is still pending.

## Package measurements

All runs used the companion fieldkit and a clean `300dad7` checkout. The development scan batch
is `20261005-142043-r24-r24-finite-names`; its seed-7 injection batch is
`20261005-142103-r24-inject7-r24-finite-names`. Comparison is with model 23's corresponding
receiver-flow batches. All five scans are complete.

| Package | Findings, model 23 → 24 | Injected hits, model 23 → 24 |
|---|---:|---:|
| Rich 15.0.0 | 1 → 1 | 58/76 → 58/76 |
| Pydantic 2.13.5 | 0 → 0 | 0/76 → 0/76 |
| Typer 0.27.2 | 5 → 5 | 55/76 → 55/76 |
| Pluggy 1.6.0 | 2 → 2 | 35/42 → 35/42 |
| Packaging 26.3 | 2 → 2 | 57/76 → 57/76 |

There are zero NEW and zero LOST findings. Existing digest-matched labels remain six true and
four false findings, with no unsure or unverified development findings. They are inherited labels,
not a new independent precision audit. Synthetic detection remains **205/346 (59.2%)**; this is
injection recall for this sample, not recall over all dead code.

The five-package holdout subset (sniffio, shellingham, uritemplate, simple_websocket, smbclient)
also has zero changed findings and five complete scans, batch
`20261005-142127-r24-r24-finite-names-subset`. Zero findings do not establish precision or recall.
The broader historical holdout is not newly verified. No speed claim is made.

## Remaining work

This milestone establishes a tested finite-value mechanism, but does **not** improve the package
score. Pydantic still needs two separate proofs: how its receiver is classified, and whether the
mutable `path_types` mapping's keys remain bounded. An opaque receiver's attribute can hold a
function with another definition name; matching definitions by name alone cannot justify narrowing.

The next bounded proposal should first collect independent cases for external receiver provenance
through conditional imports and for container aliasing, mutation, escape and rebinding. Measure which
proof is actually sufficient before implementing dictionary propagation. Keep the guard when evidence
is unknown. The four historical false findings and the low injected-method recall remain open; there
is no evidence yet for market-leading quality.
