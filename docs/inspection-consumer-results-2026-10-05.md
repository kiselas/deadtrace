# Inspection consumer summary, 2026-10-05

Model 29, final source commit `490d8a9`, distinguishes literal class-info tuples used by unshadowed
isinstance/issubclass from class registries handed to unknown consumers. Ordinary methods of the
inspected classes are no longer protected solely because the class appears inside a tuple. Nested
tuples are supported. Unknown expressions, starred elements, metaclass hooks, other escapes,
local/enclosing bindings, star imports and qualified inspector writes retain conservative fallbacks.
ADR-0042 records the semantic invariant and source-derived shadow indexes.

The independent case `inspection_classinfo_tuple` now finds `Checked.idle` while preserving
`Escaped.run`. A source archive of model 28 (`cb6c343`) fails the candidate expectation for
`Checked.idle`; the scanner did not execute either target. This establishes the local improvement,
not a general interprocedural/container model. Fourteen initial unit checks and a cross-module
qualified-write check cover the summary and its safety boundaries.

## Required checks

- Ruff check and format: 557 files.
- Mypy: 59 files each, Windows and Linux targets.
- Pytest: 490 passed, two expected skips, 93.19% coverage.
- Seed validator: 6 cases, 12 lexical targets. Corpus: 121 cases, 422 targets, all 121 semantic.
- Offline source/wheel build and installed-wheel smoke outside the checkout passed, including
  the model-29 assertion and no-target-execution sentinel. The first build stalled and was retried;
  an attempted smoke on the previous wheel was rejected by the revision assertion before success.

Linux runtime CI is not a local test result. Dependencies and public schemas are unchanged.

## Field measurements

Final clean-commit scans of ten development packages are complete: the same 10 findings as model 28,
six inherited true and four inherited false labels; no new/lost findings or pending labels. The five
holdout-subset packages remain complete with zero findings and no differences. These are regression
checks, not a fresh precision audit or competitor ranking. No speed claim is made.

| Package | Seed-7 injected definitions found |
|---|---:|
| Rich | 58/76 |
| Pydantic | 0/76 |
| Typer | 55/76 |
| Pluggy | 35/42 |
| Packaging | 57/76 |
| Click | 55/76 |
| Starlette | 59/76 |
| HTTPX | 65/76 |
| Requests | 54/76 |
| h11 | 36/71 |
| Total | 474/721 (65.7%), unchanged versus the corresponding model-28 matrices |

The summary improves the independent pattern but has no measured recall gain on this package matrix.
Pydantic's remaining descriptor reflection and h11's registry escapes are not literal inspection
tuples at the use site. Narrowing those requires carrying container/returned-value provenance to
the consumer and preserving unknown callers, writes, aliases and callback effects. A next bounded
step can propagate local immutable class-info tuple origins, with unknown/escaping uses activating
the existing broad protection; return summaries need separate context and external-caller controls.
That next step remains a proposal, with no future fixture behavior inferred or declared passing.
