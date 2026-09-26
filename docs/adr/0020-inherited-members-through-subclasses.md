# ADR-0020: Inherited members used through a subclass (model revision 14)

**Status:** Accepted, 2026-09-26.

## Context

The control pass after ADR-0019 checked the findings of one project that earlier passes had
only sampled. Three factory_boy factories were reported although tests used them:
`ToxicFileChunkModelFactory.create(...)` calls `create`, which the project base factory defines,
so the call resolved to `BaseFactory.create` and the subclass itself was never used. Its
`_create` override and `Meta`, which the base factory and factory_boy call on the subclass, were
reported as unreached.

## Decision

When a call or reference `Sub.member` resolves to a member that a base class of `Sub` defines,
`Sub` is used as well: the member runs with `Sub` as its class. A resolved field-load edge leads
from the user to `Sub`, so the hooks that bases outside the project call on it are reached through
the external-base rule of ADR-0009 and ADR-0017. pytest-click's fixtures are known plugin
fixtures (ADR-0016).

`MODEL_REVISION` becomes `python-fastapi-dishka/14`.

## Consequences

- The three factories are no longer reported; a unit test in
  `tests/test_import_roots_and_dispatch.py` checks that the subclass and its override are reached
  and that a sibling subclass nobody uses is not.
- Resolving a member through an instance of a subclass is unchanged: `_dispatch_edges` already
  reaches overrides.
