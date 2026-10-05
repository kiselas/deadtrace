# Declared public return API cycle, 2026-10-05

Model 31 (`f66df20`) retains public methods of private-module objects returned by exported
factories and public methods, using their declared project return types. `make() -> Worker`
now exposes `Worker.run`; chained methods, fields, inheritance and property contracts participate
in the existing finite API closure. The independent violation was pinned at `3cebfad` on model 30
before implementation, and its unchanged target expectations moved to corpus after the fix.
ADR-0046 specifies supported annotation forms and limits. The library-roots capability is 3;
public report/config schemas and dependencies are unchanged. Target code is never executed.

## Measurement

Clean-source fieldkit scans of ten development packages show no NEW or LOST findings relative
to model 30: six inherited true and two inherited false findings remain, with no pending labels.
This closes a demonstrated safety hole in the independent case, but shows no package-level gain
on this sample. The inherited labeled cohort is 6/8 (75%), not a fresh or market-wide precision
estimate. Seed-7 injection recall remains 474/721 (65.7%), unchanged in each package:

| Package | Detected injections |
|---|---:|
| rich 15.0.0 | 58/76 |
| pydantic 2.13.5 | 0/76 |
| typer 0.27.2 | 55/76 |
| pluggy 1.6.0 | 35/42 |
| packaging 26.3 | 57/76 |
| click 8.2.1 | 55/76 |
| starlette 0.37.2 | 59/76 |
| httpx 0.28.1 | 65/76 |
| requests 2.34.2 | 54/76 |
| h11 0.16.0 | 36/71 |

The historical five-package holdout subset is complete with zero findings, unchanged; it is a
regression check, not a fresh blind audit. No new verdicts were required or verifier identities
rewritten. Timing is recorded by fieldkit but no speed improvement is claimed.

## Verification

Ruff check/format: 571 files. Mypy Windows/Linux targets: 59 files each. Pytest: 510 passed,
two expected skips, coverage 93.21%. Validators: seed 6 cases/12 targets, corpus 123 cases/426
targets, all 123 semantic. Offline source/wheel build passed after restarting a stalled builder.
Installed-wheel smoke outside the checkout passed with an explicit model-31 assertion and
target-execution sentinel. Linux runtime CI remains unverified locally.

Controls cover Callable inputs, parameter types, Annotated metadata, Literal strings, container
arguments, private methods, conditional import alternatives, quoted/aliased annotations, returned
method cycles, property/field chains, automatic exports and explicit configured worlds.
Unannotated factories, arbitrary value/container flow, Self, assigned type aliases and builtin
type[T] remain outside this rule; pytest fixture return discovery is unchanged.

## Next measured priority

**Follow-up:** full boundary replay supersedes the selected-path hypothesis below. The returned
registry is not the cause of zero recall; _call_wrapped_attr has legitimate independent callers.
See [the reviewed diagnosis](pydantic-recall-review-2026-10-05.md) for reproduced removal/substitution
experiments and why their hypothetical +12 is not yet a justified scanner refinement.

Pydantic's 0/76 is the largest observed package-wide failure. Archived derivation tracing of a
miss shows the immediate guard is dynamic_attribute_dispatch in
PydanticDescriptorProxy._call_wrapped_attr, rather than metaclass_execution recorded upstream
in the injection ledger. A selected path reaches that method through default_ignored_types,
which returns a list converted to a tuple of classes. inspect_namespace combines that tuple
with configured ignored_types and consumes it in isinstance. Returning this class registry
currently escapes its ordinary methods, bringing a broad reflection guard into the world.

Investigate bounded interprocedural class-info container provenance and consumer summaries
with mutation, unknown-member, shadowed-builtin and arbitrary-use controls before any narrowing.
Literal/local tuple handling alone cannot explain this real list/append/tuple/return/concatenation
pattern. The trace is one selected derivation, not proof that removing it resolves all 76 misses;
the descriptor also has legitimate callers. Do not narrow guards by package-specific names or
reinterpret upstream ledger attribution as the immediate cause.
