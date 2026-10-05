# Stored reflection quality cycle, 2026-10-05

Model 27 (`b048aa8`) fixes a demonstrated unsafe finding: a method read with literal getattr and
called through a stored callback is now protected. ADR-0038 pins the violation before its fix;
ADR-0039 records the bounded semantics. The independent case moved to corpus unchanged, with an
unreferenced method as a locality control.

Verification: Ruff check/format (546 files), mypy Windows and Linux targets (59 files), 465 tests
passed with two expected skips and 93.16% coverage; seed validator 6 cases/12 targets; corpus
validator 119 cases/418 targets, all 119 semantic; offline source/wheel build and installed-wheel
smoke outside the checkout passed, including the target execution sentinel. Linux runtime CI was
not run locally. Dependencies and public schemas are unchanged.

Clean-commit fieldkit scans of five development packages are complete with the same 10 findings:
six inherited true and four inherited false labels, no new or lost findings, no pending labels.
The five-package holdout subset remains complete with zero findings. These are regression checks,
not a fresh precision audit or evidence of market leadership. No speed claim is made.

| Package | Injected definitions detected |
|---|---:|
| Rich 15.0.0 | 58/76 |
| Pydantic 2.13.5 | 0/76 |
| Typer 0.27.2 | 55/76 |
| Pluggy 1.6.0 | 35/42 |
| Packaging 26.3 | 57/76 |
| Total | 205/346 (59.2%) |

Archive-chain tracing now distinguishes the immediate guard from earlier selected ancestors.
Pydantic's descriptor proxy reflection is reached through an escaped class reference and still
opens broad protection. Initial partial keywords cannot justify reducing the names to setter and
deleter: [Python partial allows keyword overrides](https://docs.python.org/3.12/library/functools.html#functools.partial).
A regression check retains the override call. This cycle improves safety, with no measured recall
gain on this package matrix. Next, imported callable aliases exposed through a project module need
independent violation recording; local member enumeration currently overlooks them.
