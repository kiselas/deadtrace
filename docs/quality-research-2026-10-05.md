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
