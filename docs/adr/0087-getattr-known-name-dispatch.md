# ADR-0087: getattr with a known name dispatches by name

**Status:** Accepted, 2026-10-12; model revision 70.

`getattr(value, name)(...)` on a value of unknown type protected the whole graph: the model could
not say what the attribute was, so every definition became conservatively reached. In the reviewed
cohorts 80 of 362 projects had such a guard, and 73 of those reported nothing. Many of the calls
name the attribute anyway:

```python
getattr(llm, "saveState")(model_id, cache_path)
getattr(k8s_api, f"create_namespaced_{object_type}")(body=yml_object)
getattr(metadata, "validate_" + key)()
```

`getattr(llm, "saveState")()` is the call `llm.saveState()`, which dispatches by name to project
methods called `saveState` and to members of that name of modules held as values (ADR-0009,
ADR-0081). The `getattr` form now does the same: a constant or a finite set of strings dispatches
to those names, and a name with a constant start or end dispatches to every such name that fits
it. A name that is fully unknown keeps the whole-graph guard.

This supersedes point 3 of ADR-0034, which kept the broad guard for opaque receivers because
"an opaque object's attribute may hold a callable whose definition has an entirely different
name". The attribute call `value.run()` faces the same aliasing and dispatches by name already;
a callable stored under an attribute escaped where it was stored (`value.run = handler` makes
`handler` a value of an unknown consumer), a class body that binds one references it, and a
callable handed to code outside the project escaped there. The two forms now agree.

A receiver that may be a module keeps the previous rule, because a module's functions are not
methods: `sys.modules[name]`, an `import_module` result, a name bound to a project module, or a
local this scope assigns one of those.

The modules that count as values (ADR-0081) now also include a project module passed to a call
other than one that only reads it (`getattr`, `hasattr`, `isinstance`, ...), stored in an
attribute, or returned, so that `def run(plugin): plugin.handle()` with `run(plugins.csv)` reaches
`plugins.csv.handle` through either form.

The case `corpus/python/getattr_known_name_unknown_receiver` fails on revision 69.

MODEL_REVISION becomes `python-fastapi-dishka/70`.
