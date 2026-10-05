# ADR-0040: Reflection through an imported module alias

**Status:** Accepted, 2026-10-05; violation recording, model 27 unchanged.

## Context and decision

ADR-0039 is complete. The next single milestone retains imported project callables exposed through
reflected module attributes. `reflected_reexport` independently demonstrates a present contract
violation: `api` imports `worker.work as run`, and `getattr(api, "run")` returns a callable that
is subsequently executed. Model 27 reports `worker.work` as a candidate. `worker.idle` is an
unreferenced locality control. The known-violation test pins exactly `worker.py:work` before a fix.

The fix must select exported attribute names before following their imported aliases, preserve
conditional alternatives and source-local re-export chains, terminate on cycles, and remain
read-only within the source universe. Do not filter aliased callables by their definition names.
No schema, dependency, heap model, target execution or installed dependency reader is introduced.
