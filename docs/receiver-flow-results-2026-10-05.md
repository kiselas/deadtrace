# Receiver-flow milestone: verification and limits

Model 23 fixes both independently recorded safety violations: reachable methods at a branch
merge and a loop back edge are no longer candidates. Their unused controls remain candidates.
Archived model-22 source at `0d28568` fails both promoted cases. The implementation and trust
boundaries are specified in [ADR-0033](adr/0033-receiver-control-flow.md).

The user approved this single semantic milestone on 2026-10-05. Scope is local receiver types;
finite dynamic-name propagation and new framework models remain subsequent work.

## Package checks on the clean implementation commit

All runs use `fieldkit`, model 23 at clean commit `80e02a0`, sequential jobs, static source copies,
and the same cached package versions as the model-22 baseline. No target was imported or executed.

| Development package | Findings before / after | Injection hits before / after |
|---|---:|---:|
| rich 15.0.0 | 1 / 1 | 59 / 58 of 76 |
| pydantic 2.13.5 | 0 / 0 | 0 / 0 of 76 |
| typer 0.27.2 | 5 / 5 | 55 / 55 of 76 |
| pluggy 1.6.0 | 2 / 2 | 36 / 35 of 42 |
| packaging 26.3 | 2 / 2 | 57 / 57 of 76 |

Development scan batch `20261005-140308-r23-receiver-flow` has zero NEW and LOST findings against
`20261005-133647-r22-quality-20261005`. All ten existing findings have digest-matching historical
verdicts: six true, four false, zero unsure or unverified. There is no new precision claim.

Injection batch `20261005-140353-r23-inject7-receiver-flow`, seed 7, reports 205 / 346 (59.2%)
versus 207 / 346 (59.8%) in model 22. The two additional protected methods are in `rich.styled.Styled`
and `pluggy._hooks.HookspecOpts`. Their current guards originate at `rich/layout.py:229` and
`pluggy/_manager.py:255`, where inferred values reach unresolved consumers. This is an explicit
tradeoff: protecting possible instance consumers improves safety but loses two synthetic hits.
The TypedDict receiver and library-protocol consumer are development leads for later precision
of value summaries, not evidence that general recall improved. Reflection can invalidate the
assumption that an injected unique method is necessarily dead.

Five packages from the existing holdout set were checked without tuning: sniffio 1.3.1,
shellingham 1.5.4, uritemplate 4.1.1, simple-websocket 1.1.0 and smbclient 1.14.0. Batch
`20261005-140503-r23-receiver-flow-subset` is complete in all five and reports zero findings,
with zero NEW/LOST relative to the previous model-22 holdout batch. This is a subset check,
not a full holdout result; zero findings cannot establish precision or recall. The prior 80
unverified holdout findings elsewhere are still unverified.

The companion field repository retains the ledger, archived reports, injection copies and raw
`fieldkit score` output in `reports/2026-10-05-receiver-flow-score.txt`. No private project names
or paths are included here. Package copies omit installed distribution metadata and consumers
outside the source tree, so the benchmark is limited to that declared source universe.

## Verification

- Ruff check and format; mypy on Windows and with the Linux target: passed.
- Pytest with branch coverage: 379 passed, two skips, 93.00% coverage.
- Seed validator: six cases, 12 targets; corpus validator: 114 cases, 403 targets.
- Offline isolated wheel/sdist build and installed wheel smoke outside the checkout: passed.
- Baseline replay: both safety cases fail on model 22 and pass on model 23.

The skips concern Windows symlink privileges and the empty known-violation parameter set.
Linux runtime CI is not locally verified. Model-22 saved reports are method-incomparable with
model 23; report and baseline schemas, dependencies and `uv.lock` are unchanged.

## Next bounded milestone

Pydantic's zero-of-76 result remains. Start with an independent case for iteration over a fixed
dictionary of method names, plus an unknown-name control and mutation/rebinding controls. Then
introduce finite string-name sets for that proven pattern, preserving unknown fallback. Run and
review every NEW development finding before claiming a detection gain. Do not narrow guards by
assuming an external base cannot invoke methods it does not itself declare.
