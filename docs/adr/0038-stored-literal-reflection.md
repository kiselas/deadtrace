# ADR-0038: Stored literal reflection retains its callable target

**Status:** Accepted, 2026-10-05; violation recording before implementation.

## Context

The continuing quality audit found that model 26 skips a literal-name getattr value on a known
project receiver. `callback = getattr(worker, "run"); callback()` can therefore report `run` as
dead although it executes. `stored_literal_reflection` independently pins this present contract
violation with an unreferenced `idle` control; it is not an expectation inferred from fixtures.

## Decision

ADR-0037 is complete. The single next semantic milestone is preserving stored literal reflection
on known project receivers/modules. Record the violation before changing semantics. Then apply
existing conservative reflected-value protection to literal selections as well as computed names,
without broadening unknown-receiver claims or specializing Pydantic/partial by package name.

## Consequences

The implementation requires a raised model revision, a separate decision record, negative and
inheritance/alias tests, the unchanged independent case expectations, full required gates, and
clean-commit package scans/injections. Scanner paths continue to read source without executing it.
No dependency, report schema, configuration schema, or source-universe expansion is authorized.
