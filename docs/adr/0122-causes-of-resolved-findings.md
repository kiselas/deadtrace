# ADR-0122: Causes of findings that are no longer reported

**Status:** Proposed, 2026-10-21. Draft with a prototype; changes the baseline annotation of a
report and the comparison artifact (additive). Analysis and model revision 94 unchanged.

## Context

In the agent loop “edit the code, scan again”, a finding that disappears is read as code that is
gone or used. `compare` cannot tell more: it matches findings by fingerprint, and every earlier
fingerprint missing from the later report is `resolved`. Yet a finding also disappears when the
edit adds an unknown boundary, such as a `getattr` with a computed name. The candidate is then
only possibly running. Its code is unchanged, and no resolved path from a root reaches it. A
reviewer, or an agent summarizing the comparison for one, needs to know which of the two
happened. The question was raised by a reader of the project's article.

What the reports carried before this decision:

- `compare` lists new guards (`DT2002`) separately, by world and message. It does not link them
  to findings. Guards are grouped by message with a null origin by default (ADR-0079), so even a
  manual reading cannot name the new site.
- Whether a member became conservative is visible only with `--world-members`, and then without
  the boundary.
- `compare` reads only shown findings. A finding the later analysis holds back (ADR-0071), for
  example because a configuration file now mentions its name, is listed as `resolved`.
- The analysis itself knows more. `first_boundaries` attributes each conservative node to the
  unknown boundary its derivation first crossed from resolved code; it feeds the “widest guards”
  text. Each resolved derivation names the node it comes from.

Recording that attribution for every node would undo ADR-0079, which shrank the largest report
from 340 MB to 24.5 MB. Only the findings that disappeared need a cause.

## Decision

1. **Causes.** A finding that a later analysis no longer shows gets one cause. Its members get a
   status each, with evidence:

   | Cause | Meaning | Evidence |
   | --- | --- | --- |
   | `deleted` | the member is no longer in the source | — |
   | `reached` | a world that hides the finding reaches it on a resolved path | world, edge kind and the node it comes from, or the root it now is |
   | `kept` | retained, or derived from a conservative root such as a keep contract | the contract |
   | `protected` | only possibly running, through an unknown boundary | world, boundary node, place, domain and reason; the conservative caller with its edge, when there is one; `sole`; in `compare`, `new_boundary` |
   | `unexplained` | unreached and not retained, but no longer reported for another reason | — |
   | `regrouped` | the member is in another current finding | its fingerprint and code, and any blocking reasons |
   | `blocked` | the same fingerprint is held back (ADR-0071) | blocking reasons |
   | `incomplete` | a production world is incomplete, so no finding is emitted | — |

   `compare` adds `method_changed` and `unattributed` (step 4). The causes are ordered from the
   weakest evidence that the code is gone or used to the strongest. The order is `incomplete`,
   `method_changed`, `unattributed`, `blocked`, `regrouped`, `unexplained`, `protected`, `kept`,
   `reached`, `deleted`. A finding takes the weakest cause among its members. One protected
   member therefore keeps a component from reading as resolved by a consumer.

   The worlds that hide a finding follow from how it is emitted. Production worlds hide every
   code. RCH001 also leaves out what a tests world reaches, so for RCH001 tests worlds are
   consulted after the production worlds. RCH004 is defined by such reach, so for RCH004 they are
   not. A protected member names its conservative caller when it has one. It then tells a new
   call from code that may run only through the boundary apart from code that a boundary
   elsewhere covers without any call. Unknown edges and the edge from a member to its class are
   not callers.

2. **The scan records causes.** `deadtrace scan --baseline` already counts stale entries, the
   baseline fingerprints it no longer shows. While the graph is in memory it now writes
   `baseline.stale_entries`: for each stale entry, its fingerprint, code, cause and members with
   status and evidence. Members are matched to the new graph by path, qualified name, kind and
   occurrence, the identity that fingerprints hash. Text output adds a `Stale by cause` line and a
   line per entry. The size grows with the number of disappeared findings, not with the graph. A
   scan without `--baseline` writes the same bytes as before.

3. **Counterfactual.** For a protected member, `sole` tells whether the boundary alone keeps it
   possibly running. The boundary is identified by its source node and domain. `sole` is true
   when, without the boundary, no world that hides the finding reaches the member. This is the
   reviewer's question “does the finding return without this boundary?”, which differs from the
   first boundary crossed. The answer comes in three steps.
   - **Without solving.** Resolved reach never depends on unknown boundaries. Suppose another
     boundary is crossed from resolved code of a world that reaches the member, and it targets
     the member, with no gate that only conservative code opens. Then the member stays possibly
     running, and `sole` is false.
   - **Solving.** Otherwise the worlds are solved again without the boundary. Removing a
     boundary can only shrink what a world reaches, so only the worlds that reach one of the
     boundary's members are solved.
   - **Budget.** The worlds solved for all boundaries add up to at most the number of worlds of
     the analysis, about one more solve, and to at most `COUNTERFACTUAL_LIMIT` (8) boundaries.
     Past the budget, `sole` is null. The budget counts worlds, not seconds, so a report does not
     depend on the machine.

4. **The comparison reads causes.** Each entry of `findings.resolved` gains a `resolution`, and
   the summary gains `resolved_by_cause`. The causes the later report records are used first.
   Otherwise `compare` uses only what the two reports show:
   - `blocked`, when the fingerprint is among the later `blocked_findings`;
   - `regrouped`, when a member belongs to a later finding, shown or blocked;
   - `deleted`, when every member's file has left the source universe;
   - `method_changed`, with the reasons, when the reports are not comparable;
   - `unattributed` otherwise, with the advice to scan with a baseline of the earlier report.

   A protected member's `new_boundary` is true when the earlier report has no guard with the
   boundary's reason in that world. It is false when the earlier report names the boundary's node
   among that guard's origins. It is null when the earlier report lists the reason but groups the
   origins (ADR-0079), because then it cannot tell sites apart. Text output adds `Resolved by
   cause` and one line per resolved finding.

5. **Schemas.** The report, baseline and comparison schemas stay at version 1: the additions are
   new keys, and readers that ignore unknown keys see what they saw before. Exit codes,
   `--fail-on-new`, baselines and their comparability are unchanged.

## Field evaluation

Measured on 2026-10-21 on real history of the public GitHub cohorts b to h, at model revision
94. Of the 190 cohort projects with findings, 2 that take more than 120 seconds to scan were left
out, and the history of 1 could not be fetched. For each of the remaining 187 projects, the
recorded commit and the commit 30 earlier were exported with `git archive` and scanned. The
window was shorter in 10 projects, whose history is shorter; the median is 30. The earlier
report became the baseline of the later scan. Nothing was imported or executed. Of the 187
pairs, 180 were comparable, 5 partially comparable and 2 incomparable. The pairs add 346 findings
and resolve 107, in 40 projects.

| Cause | Findings | Without the scan's causes, `compare` says |
| --- | ---: | --- |
| `deleted` | 22 | 14 `deleted` (the file is gone), the rest `unattributed` or `method_changed` |
| `regrouped` | 25 | 25 `regrouped` |
| `blocked` | 22 | 22 `blocked` |
| `reached` | 16 | `unattributed` or `method_changed` |
| `protected` | 22 | `unattributed` or `method_changed` |

Without the scan's causes, 43 of the 107 findings stay `unattributed` and 3 read as
`method_changed`. Before this decision, `compare` counted all 107 as resolved. At least 44 of
them are not gone or used: 22 are only possibly running and 22 are held back.

- **Blocked.** 21 of the blocked findings are in one project that added mkdocstrings pages in
  the window, so `public_api` holds them back (ADR-0071). The remaining one is
  `mentioned_in_config`.
- **Protected.** The 22 protected findings have 38 protected members. 20 of the members are
  protected in the tests world. For 13 members the boundary is `sole`, for 24 it is not, and for
  1 the answer is null. `new_boundary` is true for 27 members and null for 11, where the earlier
  report groups the guard's origins. The boundary domains are dynamic `getattr` 16, escaped class
  9, unresolved method dispatch 6, escaped reference 4 and escaped callable 3.
- **Reached.** 17 members are reached by a call and 16 because they are now roots (11 by
  framework discovery). The rest come through dependencies, constructors and annotations.

The first version of the prototype classified 15 findings, 32 members, as `unexplained`. All of
them were reached by the tests world, which hides RCH001: 10 on a resolved path and 22 only
conservatively. The tests worlds were added for RCH001 for this reason. After that change, none
is unexplained.

**Hand check.** Each label was checked against the source at both commits.

- 4 of 4 `deleted` members are gone at the later commit.
- The `blocked` project added `:::` documentation pages in the window.
- 2 `reached` findings were checked. One gained a call in the window. In the other, the named
  caller is unchanged and code further up its path became reachable: the evidence names the
  immediate caller, not necessarily the edit.
- 7 `protected` findings were checked. In 3, the code is unchanged and used only by tests; a new
  dynamic `getattr` in another module hides it, the case that motivated this decision. In 4, a
  new call appeared in the window, but from code that may itself run only through a boundary:
  - a `threading.Thread` target;
  - an `asyncio.to_thread` target;
  - a callable used as a value by an unknown consumer;
  - a method called on a value of unknown type.

  That split is why protected members now name their conservative caller.

**Cost.**

- On the 40 projects with resolved findings, attributing causes took 2.1 seconds in all and at
  most 0.3 seconds per project. That is a median of 0.5 % and at most 2.4 % of the later scan.
  The 12 counterfactual solves took 0.4 seconds in all.
- The first prototype solved every production world for each of 8 boundaries. On the project
  with 299 worlds that took 39 to 108 seconds per boundary, 530 seconds in all, against 169
  seconds for its analysis. No member was sole.
- With the check without solving, 36 stale entries per project were built from the widest
  boundaries of that project and of a project with 39 worlds. 60 of them were protected; the
  other 12, in the 299-world project, were kept. All 60 were settled without a solve, in 0.4
  seconds per project, against analyses of 113 and 176 seconds.
- With the check switched off, the budget allowed one solve, 64 and 56 seconds. That is the worst
  case: about 1.2 to 1.3 times the solve stage and 38 to 69 % of the analysis.

The scans ran one at a time on a development machine. A disk-heavy job ran during the first
history pass and the first cost run, so their absolute seconds may be high; the ratios within a
process are not affected.

## Consequences

- On small projects, an added `getattr(module, name)()` turns two candidates into `protected`
  findings, naming the boundary at `main.py:9`, `sole` and new. A new call turns one candidate
  into `reached` from `main.live` and leaves the other unchanged. A name that a YAML file now
  mentions is reported as `blocked`, not resolved. `tests/test_resolution.py` covers:
  - each cause, including reach from the tests world and a caller behind a `threading.Thread`
    boundary;
  - the second boundary that makes neither member sole;
  - the budget;
  - the novelty rules;
  - the scan's text output.
- To attribute a comparison, the later scan needs a baseline made from the earlier report. In
  the agent loop that is one more step: `baseline create` on the earlier report, which also asks
  for a reason.
- In the worst case the counterfactual adds about one solve to a scan with `--baseline` and stale
  entries. In the field it added almost nothing, because a second boundary settles most members
  without a solve.
- Nothing changes for findings that stay, and scanner semantics are unchanged, so no reviewed
  public findings were re-measured.

## Open questions

- Should `scan --previous REPORT` take a saved report directly, so the agent loop needs no
  baseline? The causes are facts of the later graph and do not depend on where the entries came
  from.
- `baseline update` drops the entry of a finding that became `protected`. When the boundary is
  removed, the finding returns as new and fails `--fail-on-new`. A protected entry could be kept
  as dormant instead.
- `new_boundary` is null for 11 of 38 protected members, because reports group guards by message.
  The later scan could instead record whether the boundary's source existed in the earlier
  baseline's members or files.
- `reached` names the immediate caller, which need not be what the edit changed.
- RCH002 and RCH003 are classified by the reachability of their members. A router that an
  unresolved `include_router` may include (ADR-0072) is the same kind of caution and should read
  as `protected`.
