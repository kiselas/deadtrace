# Quality audit and research, 2026-10-05

This is a development audit, not a market ranking. The active milestone remains inventory-only
PR-01 as instructed in `AGENTS.md`. Model 22 already exists in the checkout; this cycle records
violations and improves operational reliability without promoting a new semantic milestone.

## Findings that affect the next algorithmic step

Two independently specified examples now live in `fixtures/known-violations/` and are pinned in
`tests/test_known_violations.py`. Neither target is imported or executed during analysis.

| Construct | Incorrect candidate in model 22 | Independent evidence |
|---|---|---|
| Alternative receiver assignments in `if/else` | `First.run` | main is called with both Boolean values |
| Receiver changes across a loop back edge | `Second.run` | two iterations call the two methods in order |

Both cases require an unrelated unused control to remain a candidate. A project-wide guard would
hide the symptom while destroying recall. This is a safety defect, not a preference about public
library APIs. `_ExecutionVisitor.local_types` stores one type per local; `_visit_assign` replaces
that type. A syntax traversal does not join branch environments or iterate loop environments to a
fixed point. Adding more framework names cannot repair this problem.

The private field ledger, inspected read-only in this cycle, also contains an evaluation gap:
the latest historical holdout scan has 80 findings without verdicts. No holdout precision is
available. Development precision and injection recall are useful diagnostic evidence, but do
not establish market leadership. Detailed target identities stay outside this repository.

## Fresh package measurements

`fieldkit` scanned existing pinned development copies on clean commit `2dd21bd`, model 22,
with `--jobs 1`. Scan batch: `20261005-133647-r22-quality-20261005`; injection batch:
`20261005-133709-r22-inject7-quality-20261005`, seed 7. No target code executed.

| Package | Findings | Injected definitions reported |
|---|---:|---:|
| rich 15.0.0 | 1 | 59 / 76 |
| pydantic 2.13.5 | 0 | 0 / 76 |
| typer 0.27.2 | 5 | 55 / 76 |
| pluggy 1.6.0 | 2 | 36 / 42 |
| packaging 26.3 | 2 | 57 / 76 |

All five scans were complete. There were zero NEW and zero LOST findings against the previous
model-22 batch for these targets. Existing source-digest verdicts account for all ten findings:
six true, four false, no unsure or unverified findings. This small development sample has 60%
finding precision under those inherited verdicts; it is neither a fresh blind review nor a
holdout estimate. The two false findings in packaging concern historical pickle compatibility
classes; the two in pluggy concern tracer methods used by pytest through a public instance path.
Their mechanisms were already recorded, and the current sources confirm the consumers.

The injection harness reported 207 / 346 (59.8%). Functions and new classes each scored
44 / 56; methods in existing project-base classes scored 19 / 55, external-base classes
25 / 62, and no-base classes 30 / 59. These are synthetic detection rates, not general recall.
Reflective consumers, API policy, omitted distribution metadata and external consumers limit
what can be inferred from source-only package copies.

Pydantic's broad guard at `pydantic/v1/utils.py:661` accounts for 60 of its misses: `path_type`
iterates a fixed dictionary of filesystem method names and calls `getattr(p, method)()`. The
guard spreads far beyond those names. A finite string-value domain for such iteration can
constrain dispatch without assuming a type annotation is enforced at runtime. This is a
specific development case for step 3 below, with an unknown-name safety control required.

The ledger and archived reports remain in the companion field repository. Its
`reports/2026-10-05-package-quality-score.txt` is the output of `fieldkit score`, not a new
unrecorded analyzer run. No private target names or paths are copied here.

## Verification of this cycle

Ruff check and format, mypy on Windows and with the Linux target, pytest with branch coverage
(353 passed, one Windows symlink-permission skip; 92.79%), both required case validators, and
the known-violation validator passed. Build succeeded offline using cached isolated build
dependencies; the online attempt was stopped after stalling. The installed wheel passed the
portable smoke check outside the checkout, including no target execution. Linux runtime CI
has not been run locally. No dependency, lock, model revision, or report schema changed.

## Research and tools

| Source | Approach | Consequence for Deadtrace |
|---|---|---|
| [PyCG paper](https://arxiv.org/html/2103.00587v1) | Interprocedural assignment graph, context-insensitive fixed-point iteration, then call resolution | Track sets of possible values through assignments, parameters and returns; measure call edges separately from dead definitions |
| [JARVIS paper](https://arxiv.org/abs/2305.05949) | Per-function type graphs, flow-sensitive intraprocedural analysis and on-demand interprocedural construction | First implement control-flow joins correctly; restrict strong updates to assignments that occur on every relevant path |
| [Vulture algorithm and limitations](https://github.com/jendrikseipp/vulture/blob/main/README.md) | AST definition/use names without scope; whitelists and confidence by object kind | Useful name-based comparator; name collisions and implicit callbacks require separate labels. Its percentages are not calibrated probabilities |
| [Skylos tools](https://github.com/duriantaco/skylos/blob/main/README.md) and [benchmark](https://github.com/duriantaco/skylos/blob/main/BENCHMARK.md) | Static scanning, optional traces and model-assisted review; labeled benchmarks | Compare static modes on identical roots and labels. Vendor demos and synthetic results are not independent package precision; unresolved labels must stay in the denominator |

Paper call-graph precision/recall measures edges, not safe deletion. Missing call edges are
particularly dangerous for a dead-code finder: they can create false findings. Runtime coverage
can prove use when a body executes; an unexecuted body is not proof of deadness. Optional runtime
evidence remains a separate future trust decision, never part of scanner execution.

## Ordered improvement plan

1. **Safety before breadth:** accept one bounded semantic milestone for receiver flow. Add a
   control-flow representation with branch joins, loop back edges, break/continue, exceptions and
   finally. Values are finite sets of possible project types/callables plus explicit unknown, not
   one last-seen name. Convergence limits must widen to unknown rather than drop possibilities.
   Exit: both recorded violations disappear and their unused controls remain findings; add
   branch-order and loop-iteration metamorphic tests before promotion to the corpus.
2. **Evaluation coverage:** finish independent holdout verdicts, report true/false/unsure/unverified
   counts, and keep package versions and source digests pinned. Expand injection contexts by kind,
   base, roots and world completeness. Injection names alone do not prove deadness when a reflective
   consumer can enumerate arbitrary methods; classify such probes separately.
3. **Value propagation:** interprocedural parameter/return sets and container elements, followed by
   receiver-local dynamic dispatch. Compare resolved edges and protection breadth on development
   packages. Narrowing guards is accepted only with safety controls and fresh holdout evidence.
4. **Framework coverage:** versioned conventions matrices for pytest/unittest, Click/Typer,
   Pydantic/FastAPI, Django/DRF and Celery. Model registrations, roots, lifecycle and string dispatch
   separately; test the supported version interval, not only one installed version.
5. **Dependency summaries:** investigate static summaries after accepting their trust-boundary ADR.
   A method name absent from an external base is insufficient evidence of deadness: a base may
   invoke computed names or pass the instance to another consumer. Preserve unknown fallback.
6. **Comparable competitors:** pinned Vulture and Skylos static modes, same source universe and
   definition-level labels; count abstentions, failures and unverified cases. Public APIs, tests
   and application roots must have the same declared policy. Do not compare raw finding totals.

Each algorithm change needs its own ADR, model revision, previous-version failing cases, and
verified NEW findings. Keep holdout read-only for tuning until formally rotated into development.
No claim of improved detection precision or recall is made for the input-reader fixes.
