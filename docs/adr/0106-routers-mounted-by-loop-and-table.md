# ADR-0106: Routers mounted in a loop or from a table of module names

**Status:** Accepted, 2026-10-12; model revision 89.

`RCH002` reports a router that no application includes. A router counts as possibly included when
code refers to it other than through its own route decorators: an import of it, or `module.router`
after an import of the module (ADR-0072, ADR-0077). Two common mounting forms escaped that:

```python
for module in (setup, users, collections):
    app.include_router(module.router, prefix="/api")

_V1_ROUTERS = [("app.api.v1.auth", "router", "Auth"), ...]
for module_path, attr_name, tag in _V1_ROUTERS:
    app.include_router(getattr(importlib.import_module(module_path), attr_name))
```

In the blind eighth cohort every reviewed `RCH002` finding (14, in two projects) was such a router,
verdict false.

- An attribute read `variable.router` in the body of a `for` loop whose target is `variable` and
  whose iterable is a literal tuple, list, or set of names bound to imported modules reads the
  router of each of those modules.
- A string constant anywhere in the project that equals the name of a router's module, or names it
  before a `:`, marks that router as possibly included, as a table of module names mounted by
  `import_module` does.

Both only make a router possibly included; they add no finding.

The case `corpus/frameworks/routers_mounted_by_loop_and_table` fails on revision 88.

MODEL_REVISION becomes `python-fastapi-dishka/89`.
