# ADR-0006: Known contract violations are recorded as pinned failing cases

**Status:** Accepted, 2026-09-24.

## Context

The analysis contract says a finding in a complete world means no execution path was found, and
the README says unsupported dynamics weaken the affected world instead of producing stronger
negative findings. Probes run on 2026-09-24 showed complete worlds that still report code that may
run: functions stored in a registry and called through it, a returned function reference, the base
class of a constructed class and its inherited method, an override called through a base-class
annotation, a method called on the result of an unannotated factory, functions registered by a
decorator of an unmodeled framework (Celery), and the seed case `escaped-callback-helper`, whose
`CASE.md` requires protection but whose expectation is only checked lexically because it has no
world.

None of these belongs in `corpus/`: `deadtrace cases validate corpus` requires every expectation to
hold, and the corpus records modeled behavior. Leaving them out of the repository would lose the
evidence and let the next change regress silently. `CONTRIBUTING.md` forbids turning future
semantics into passing tests; these are present violations, and the roadmap asks for a failing
case to be recorded before a model fix.

The corpus vocabulary also forces a modeling choice on such a case. A registry-dispatched function
is `live` under a precise model and `protected` under a conservative one; either is safe, and the
case should not decide between them before the fix is designed.

## Decision

1. Violations live in `fixtures/known-violations/<case>/`, each a minimal target program with
   `CASE.md`, `CASE.toml`, and a `pyproject.toml` that configures its world. Expectations are
   written from the program and the safety argument, never from Deadtrace's output. There is no
   `[analysis]` table: the limitation codes a fix will produce are not known in advance.
2. `CASE.toml` gains the expectation `not_candidate`: the target is in no finding. It is the
   safety-only expectation for code that may run when the right modeling outcome is still open.
   Where the fix must stay local, the case adds a `candidate` control target that nothing
   references, so weakening the whole world cannot satisfy it.
3. `deadtrace.case_validator.unmet_targets` checks every target of a case and returns the unmet
   ones instead of stopping at the first. `tests/test_known_violations.py` pins that list per case.
   A fix removes entries, a regression adds them, and either change updates the pinned list in
   the same commit. The pinned lists are a ratchet over current behavior, not expectations.
4. A case with no unmet target moves to `corpus/` with the `[analysis]` table of the model revision
   that fixed it, and its entry leaves the pinned list.
5. Ruff ignores `fixtures/known-violations`, as it ignores `fixtures/cases`.

## Consequences

- Eight cases and twelve unmet targets are recorded. Every world in them is complete and carries no
  limitation, so each unmet target is a candidate the contract does not allow.
- The README's support claims link to these cases; `python.direct-flow` stays `modeled` but is no
  longer presented without its known violations.
- `not_candidate` is available to the corpus too, for safety cases where the modeling outcome is
  deliberately left open.
- Schema version 1 of `CASE.toml` is unchanged; the new expectation is an added value that older
  manifests never use.
