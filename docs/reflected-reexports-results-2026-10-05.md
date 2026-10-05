# Reflected re-exports and broader package checks, 2026-10-05

Model 28 (`cb6c343`) fixes another demonstrated unsafe finding: a callable retrieved from a
module's imported alias is protected under its original definition name. ADR-0040 pinned the
violation before changing semantics; ADR-0041 records the source-local export traversal. Literal
and computed names, conditional imports, renamed chains, star re-exports and cyclic exports are
covered. The independent case expectations are unchanged; the unreferenced control remains a
candidate. Model 27's literal reflected-value fix remains covered.

The private field tool also has archived guard-chain tracing with eight passing tests. It separates
immediate unknown boundaries from earlier selected ancestors and explicitly reports missing
predecessors or budget truncation. A selected explanation is not an enumeration of every path.

## Verification

Ruff check/format: 553 files. Mypy: Windows and Linux targets, 59 files each. Pytest: 475 passed,
two expected skips, 93.17% coverage. Seed validator: 6 cases/12 targets. Corpus validator: 120
cases/420 targets, all 120 semantic. Offline build and installed-wheel smoke outside the checkout
passed, with an explicit model-28 assertion and target execution sentinel. Linux runtime CI was
not executed locally. No dependency, report/config schema or scanner execution boundary changed.

## Field results

All measured scans use clean commit cb6c343. The existing five development packages remain complete
with 10 findings (6 inherited true, 4 inherited false); NEW 0, LOST 0, pending 0 versus model 27.
The same five holdout packages remain complete with zero findings and no difference. No holdout
finding informed these fixes. No fresh market precision estimate or speed claim is made.

| Development package | Seed-7 injected definitions detected |
|---|---:|
| Rich 15.0.0 | 58/76 |
| Pydantic 2.13.5 | 0/76 |
| Typer 0.27.2 | 55/76 |
| Pluggy 1.6.0 | 35/42 |
| Packaging 26.3 | 57/76 |
| Existing matrix | 205/346 (59.2%), unchanged |
| Click 8.2.1 | 55/76 |
| Starlette 0.37.2 | 59/76 |
| HTTPX 0.28.1 | 65/76 |
| Requests 2.34.2 | 54/76 |
| h11 0.16.0 | 36/71 |
| Additional breadth | 269/375 (71.7%) |

Additional packages have complete scans with zero findings and no pending labels. Their injection
results establish breadth, not improvement against model 26/27: those versions were not rerun on
this additional matrix. Zero findings do not prove a package contains no dead code.

## What prevents stronger recall

Pydantic remains at zero. The selected chain reaches descriptor reflection through an escaped class
returned by `default_ignored_types`. h11 has a different immediate pattern: sentinel/event classes
held by module-level escaped-reference protection. Improving only reflected name selection cannot
resolve both patterns. Removing either guard without modeling how the values are consumed would
trade away protection for possible callbacks and methods.

The next productive research direction is interprocedural value provenance: distinguish a class
used for type inspection from one whose methods may be invoked; propagate receiver/callable origins
through returns and containers; then model descriptor/partial transfers with caller keyword overrides
and unknown external callers. Unknown writes, escapes and exhausted budgets must retain broad
protection. This is a proposal, not implemented semantics or inferred future fixture expectations.

[PyCG](https://arxiv.org/abs/2103.00587) constructs call targets from interprocedural assignment
relations. [JARVIS](https://arxiv.org/abs/2305.05949) uses function type graphs and alternating
flow-sensitive intra/interprocedural analysis with strong updates. Those approaches motivate the
proposal; their call-graph benchmark metrics are not dead-code precision/recall figures for Deadtrace.
