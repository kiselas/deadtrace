# Public object field API cycle, 2026-10-05

Model 30 (`8a64949`) fixes externally callable public methods exposed through another public
object's fields. The independent violation was pinned at `9aadb5d` before changing semantics;
its unchanged target expectations moved to corpus after the fix. ADR-0044 describes automatic
library/export root closure over source-known public field types and project inheritance.
The library-roots capability is now revision 2; public report/config schemas are unchanged.

## Observed improvement

Clean-commit fieldkit scans of the same ten development packages show exactly two lost findings,
both inherited confirmed false findings: Pluggy's TagTracer.setwriter and TagTracer.setprocessor.
They are externally callable through PluginManager.trace.root. No package-specific rule was added.
The six inherited true findings remain; the two Packaging old-pickle compatibility findings remain
false. There are no new findings or pending labels. Thus the existing labeled cohort changes from
6 true/4 false to 6 true/2 false (60% to 75% among these findings), not a fresh precision audit or
market-wide estimate. The broad external-caller mechanism remains open; only the public-field
submechanism is fixed. No verifier provenance was rewritten.

Seed-7 injections remain unchanged at 474/721 across the ten packages, including 35/42 for Pluggy.
Pydantic remains 0/76. The five-package holdout subset remains complete with zero findings and no
differences; no holdout finding informed this fix. No speed claim is made.

## Verification

Ruff check/format: 564 files. Mypy Windows/Linux targets: 59 files each. Pytest: 498 passed,
two expected skips, coverage 93.21%. Seed validator: 6 cases/12 targets; corpus: 122 cases/424
targets, all 122 semantic. Offline build and installed-wheel smoke outside the checkout passed,
including an explicit model-30 assertion and target-execution sentinel. The first build stalled
and was retried successfully. Linux runtime CI was not executed locally.

Controls cover private fields/methods, unrelated classes, explicit script roots, exports next to
a framework application, inherited fields/methods, cyclic fields, Final and quoted annotations.
The existing field inference and annotation contract are reused; opaque fields, arbitrary heap
aliases, return/container value propagation and serialization compatibility are not claimed fixed.
The local tuple-alias proposal was deferred to prioritize this demonstrated package safety defect.
