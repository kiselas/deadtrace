# Methodology and improvement track (draft)

**Status:** proposal, 2026-09-29. Not an ADR: it changes no semantics. Decisions that follow from it
(a dependency-source reader, confidence tiers, an evidence import) each get their own ADR.

Reviewed during the 2026-10-01 repository audit. This inherited draft is a research proposal,
not an accepted milestone or implementation commitment. On 2026-10-05 the user approved replacing
the inventory-only working milestone with the bounded receiver-flow milestone in
[ADR-0033](adr/0033-receiver-control-flow.md), now completed. The user approved the next bounded
finite-local-name milestone in [ADR-0034](adr/0034-finite-local-dispatch-names.md), now completed.
External receiver reflection provenance in [ADR-0036](adr/0036-localize-external-value-reflection.md)
is complete. Standard nominal families in
[ADR-0037](adr/0037-standard-nominal-reflection-families.md) are complete. The stored-literal
milestone in [ADR-0039](adr/0039-preserve-stored-literal-callables.md) is complete.
Reflected module re-exports in [ADR-0041](adr/0041-reflected-module-export-graph.md) are complete.
The current bounded milestone summarizes literal class-info tuples consumed by inspecting builtins
in [ADR-0042](adr/0042-literal-classinfo-consumer-summary.md).
Other proposed tracks remain unaccepted.
See [the audit and improvement plan](audit-2026-10-01.md) for current repository checks.

## Goal

The most precise dead-code finder for Python, one that also finds most of the dead code, is fast, and
knows the frameworks people use. Four claims have to be measurable, or they are slogans:

| Claim | Metric | How it is measured |
|---|---|---|
| Precise | share of reported definitions independently judged unused | verification by reading, and deletion oracle (below) |
| Finds most problems | share of dead definitions reported | injection, and deletion-safe ground truth |
| Fast | seconds per 100k lines, cold and incremental | benchmark from the built wheel |
| Framework-aware | share of a framework's constructs that a pack models | conventions matrix (below) |

## Where we are (measured)

- **Development evidence:** ADR-0017 through ADR-0029 report repeated field checks and fixes.
  Their projects and samples are development evidence, not a held-out precision estimate.
- **Precision on code we did not tune on is the real number.** Each new set of installed packages
  still showed a substantial false share before its fixes: 44 of 88 (50%), then 29 of 86 (34%), then about a third
  of 299. These are different samples rather than a controlled trend. The fixes address mechanisms, and the
  supply of mechanisms is not exhausted.
- **Recall:** injected functions and classes are found in every project. Injected methods of existing
  classes are found in 5% to 93% of cases by project; classes with a base outside the project (Django REST
  framework, Celery, dependency-injection containers) keep all their methods by design.
- **Private comparison, not reproduced by this audit:** vulture finds all injected names, because it matches names,
  and 47% of its definition findings on six projects are definitions that a resolved call path reaches.
  Other tools were not run.
- **Historical speed evidence:** a CI budget of 30 s for a generated 50k-line project exists. A roughly 750-finding monorepo took
  about 70 s and wrote a report of over 100 MB in ADR-0022. There is no incremental mode.

The private comparison and injection figures are inherited observations; the scripts and inputs
are not in this repository. This audit did not reproduce them. ADR-0025 through ADR-0029 support
the reported false-finding mechanisms, while ADR-0027 records a bounded method-injection sample.

## Method

### 1. A scoreboard that cannot be gamed

1. **Held-out discipline.** Sets are either *dev* (mined for mechanisms, fixed against) or *holdout*
   (scanned and verified, never fixed against until retired to dev). Precision is quoted from the
   holdout only. Without this, every number we publish is a fit.
2. **Public benchmark.** Pin 60 to 100 open-source projects and packages by version, split across
   library, web application, CLI, data, and test-heavy shapes. Field projects stay private and are
   used as a second opinion, not as the benchmark.
3. **Deletion oracle (precision at scale).** A future opt-in isolated runner, with an accepted threat
   model and separate execution authorization, could delete the definition in a copy, then
   import the package, run type checking, and run the tests where they exist. A failure proves the
   finding false, cheaply and without a reader. It cannot prove a finding true (untested code deletes
   cleanly), so it is a lower bound on false findings and is combined with sampled reading.
4. **Deletion-safe ground truth (recall).** Definitions that no test executes (coverage) and whose
   deletion breaks nothing are the recall target. It over-approximates dead code, so recall against it
   is reported with the injection recall, which under-approximates.
5. **Injection matrix.** Extend the injection harness: kinds (function, class, method, property,
   nested, decorated), base kinds (none, project, standard library, each framework), and contexts
   (reachable module, library public API, test file). Report a table, not a total.
6. **Differential runs.** Run the closest tools on the benchmark and diff the findings. Every
   disagreement is triaged into a mechanism or a documented difference. This is where unknown
   mechanisms surface first.
7. **Regression gate.** The scoreboard runs in CI on the dev set (findings must not change without an
   ADR) and nightly on the holdout (precision must not fall).

### 2. Mechanism loop (what cycles 6 to 11 did, made routine)

scan a new set, then verify every finding with the oracle and sampled readers, group by mechanism,
reproduce in a small project, fix, add a corpus case that fails on the previous revision, re-run the
holdout, record an ADR. Track *mechanisms found per 100 packages*. The goal of the track is to make
that number fall; it is the honest signal that we are converging rather than fitting.

### 3. Framework packs

Today framework knowledge is spread through the analyzer as code. It should become a **pack** per
framework: a declared list of the constructs that make code run without a visible call, checked
against the framework's own source and documentation.

A pack answers, for one framework:

- roots: entry points, commands, configuration files, deployment names it reads
- registrations: decorators and calls that register a callback (routes, tasks, signals, hooks, events)
- base classes: which members a subclass may override and the framework calls, and which conventions
  by name it applies (`validate_<field>`, `get_<name>`, `clean_<field>`, `test_*`)
- string dispatch: dotted paths in settings, `module:attr` strings, entry-point groups
- lifecycle and generated code the framework creates (models, migrations, fixtures)

Each pack has a conventions matrix (construct, modeled or not, corpus case, oracle result) so
coverage is a table anyone can read. A framework is *supported* when its matrix is fully modeled or
explicitly guarded and it passes the deletion oracle on the benchmark projects that use it.

Priority order, by how much Python code depends on it and by what the field passes found:
Django and Django REST framework, pytest and unittest, FastAPI/Starlette and Pydantic, Celery,
SQLAlchemy and Alembic, Flask, Click and Typer, `dependency_injector`, aiohttp, Airflow, Scrapy, and
chat-bot libraries.

### 4. Learn hooks from the installed dependency, do not hand-write them

The largest recall loss is the guard on classes whose base is outside the project: every method is a
possible hook. The base's own source says which names it can call. Reading the base class statically
(never importing it) from the target's installed packages, or from a pinned data file for the common
bases, turns that guard into "methods whose names the base defines, plus decorated ones, plus the
pack's name conventions". This needs an ADR (it reads files outside the scanned tree, with the same
trust rule as target metadata) and a fallback when the environment is absent.

### 5. Evidence import (optional, strong)

Consider accepting a coverage data file under a separate ADR. Executed lines provide positive
evidence of use. A definition that no world reaches and no run executed remains a review candidate;
absent coverage does not prove deadness. Static analysis then explains the rest.
This is the cheapest way to lift precision on hard mechanisms (string dispatch, generated code) without
modeling each one.

### 6. Confidence tiers

Investigate evidence tiers after measuring a held-out baseline. Passing a deletion experiment
cannot justify a "certain" or "safe to delete" tier: tests can miss external consumers. Definitions
kept by a guard remain protected, rather than becoming negative findings. Any tier policy must
preserve these rules and be accepted in its own ADR before changing reports or CI policies.

### 7. Speed

Profile first (the baseline is unknown at 100k lines). Then, in the order of expected gain:
per-file summaries cached by content hash so an incremental run parses and resolves only changed files
and what depends on them; parse in parallel; make the report proportional to findings, not to the
graph (the 100 MB report is the largest cost on big projects); avoid recomputing guards per world.
Targets are set after the profile, and enforced by the existing performance budget.

## Track

| Phase | Work | Exit criterion |
|---|---|---|
| 0. Scoreboard (2 weeks) | public benchmark with dev/holdout split; deletion oracle; injection matrix; differential runner; CI gates | one command prints precision, recall, speed, and matrix; holdout numbers recorded as baseline |
| 1. Recall on framework bases (3 weeks) | dependency-source reader (ADR); packs for Django and Django REST framework, unittest/pytest name conventions; confidence tiers | injected-method recall at least 90% on projects using those bases with holdout precision not lower |
| 2. Packs, breadth (6 weeks) | Celery, SQLAlchemy/Alembic, Flask, Click/Typer, `dependency_injector`, aiohttp; conventions matrix per pack | each pack fully modeled or guarded, oracle-clean on its benchmark projects |
| 3. Speed (3 weeks, can overlap) | profile; content-hash cache; parallel parse; smaller reports | budget set from the profile; incremental run at a fraction of a cold run |
| 4. Evidence (2 weeks) | coverage import; top-tier definition uses it | precision on hard mechanisms rises without new models |
| 5. Convergence | rotate holdout to dev, scan new holdout | mechanisms per 100 packages falls three sets in a row; holdout precision at or above the target |

Targets to fix after Phase 0 measures the baseline, not before: holdout precision, recall by kind,
seconds per 100k lines cold and incremental.

## Risks

- **Overfitting to the benchmark.** The holdout discipline and the rotation are the guard. A fix that
  moves only the dev set is not a result.
- **Precision against recall.** Every recall gain (narrowing a guard) can add false findings. Each such
  change ships with its deletion-oracle result on the holdout, not with the dev set alone.
- **Pack drift.** Frameworks change. Packs record the versions they were checked against, and the
  matrix is re-run when a pinned version moves.
- **Reading dependencies.** The dependency-source reader widens the trust boundary; it stays read-only,
  bounded in size, and optional.
