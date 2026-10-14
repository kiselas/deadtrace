# ADR-0118: Collect resolver syntax projections in one module walk

**Status:** Accepted, 2026-10-14. Frontend runtime only; model revision remains 93.

## Context

Resolver initialization separately walks every module to find star imports and
nominal name rebindings. The first scope-classification query walks that same
module again to mark functions containing a walrus, global/nonlocal declaration,
or comprehension. An owned function containing 500 calls makes the same expression
payload participate in three traversals, even though these facts are independent
projections of the same immutable syntax tree.

## Decision

Collect all three projections in one explicit worklist traversal during resolver
initialization. Retain only the existing immutable name/id sets and star-import
flag. The temporary per-module records and worklist do not outlive initialization;
there is no global cache or retained second tree.

Preserve the existing lexical boundaries: stores anywhere in the module count;
scope constructs mark all enclosing functions, including constructs in nested
classes, decorators and defaults. Class boundaries do not clear enclosing function
ids. Dotted stores whose receiver is not a name/attribute chain remain excluded.
Traversal order does not affect these set-valued projections. Scope classification
is now eager even for a module with no later query, which must be included in the
runtime measurements.

No target imports/execution, parser, framework rule, source-universe, dependency,
report schema or semantic change is introduced. Published ASTs remain immutable.
MODEL_REVISION stays 93.

## Verification and acceptance

The independent work-bound test observes one traversal of a 500-call expression
payload across initialization and repeated scope queries; the parent visits it
three times. Boundary tests check nested/async functions, nested classes, star
imports, global/nonlocal declarations, comprehensions, assignment expressions,
decorators/defaults and computed receivers.

All 358 fixed default/world-members corpus reports must remain byte-identical,
as must reviewed modern-stack text/JSON reports and seed-7 injection identities
and outcomes. Run all local quality/build/wheel gates and supported-platform CI.
Acceptance requires fresh-process alternating paired measurements including both
time and OS peak RSS. Fewer traversals alone does not prove a speed improvement.

## Evaluation and acceptance

Control `41fecef` and candidate `339532a` used CPython 3.12.4 on Windows with the
same locked runtime, files and configuration. Eight reviewed modern-stack inputs
were measured in separate text and JSON series, two alternating fresh-process
pairs each. All 64 report outputs matched byte-for-byte; the fixed 358 corpus
reports also matched. Exact seed-7 injection identities and reported flags stayed
at 534/721 development and 964/1565 holdout. Local quality/build/wheel gates and
all supported-platform CI checks passed on the source candidate.

One large FastAPI application had median local time ratios 0.909 in text and
0.935 in JSON, with essentially unchanged peak RSS. Across eight inputs, text
ratios ranged from 0.909 to 1.288 and JSON from 0.878 to 1.019. Preserve the text
slowdowns of 5.0% on the second large application and 28.8% on a FastAPI template.
A separate four-pair text repeat gave ratios 0.986 and 0.964 for those inputs;
all 16 repeat reports matched. Large variation within the unchanged control
prevents treating small timing differences as stable effects. Across both full
series, median paired RSS ratios ranged from 0.989 to 1.005.

Accept removal of redundant traversals with unchanged reports, injection outcomes
and memory use. The first large-input result and template repeat support a local
runtime benefit; these mixed samples do not establish a general speed gain or
resource superiority over another analyzer. No causal explanation is assigned to
the anomalous timings, and none of the original measurements is discarded.
