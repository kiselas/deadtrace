# ADR-0096: Modules imported by computed names are values

**Status:** Accepted, 2026-10-12; model revision 79.

`module = import_module(name)` followed by `module.check()` in the same function already reaches
the `check` of any module (ADR-0017). A loader usually returns the module instead:

```python
_BACKENDS = {"langfuse": "app.integrations.langfuse.backend"}


def _load_backend(name):
    return importlib.import_module(_BACKENDS[name])


backend = _load_backend(args.backend)
backend.build_eval_command(args)
```

`backend` is a value of unknown type, so `backend.build_eval_command` dispatched by name to methods
and to modules held as values (ADR-0081, ADR-0087, ADR-0091), and a module imported by a computed
name was none of them. In the blind seventh cohort two functions of one project were reported this
way, verdict false; the class recurs in every reviewed cohort.

The modules that a computed import may reach are now held as values: those whose names start with
the constant start of the computed name (`import_module(f"app.plugins.{name}")` reaches
`app.plugins.*`), or every module when the name has no constant start or is relative.
`sys.modules[__name__]` is the module itself. Name dispatch on values of unknown type then includes
their top-level definitions of the called name. On the recall injections nothing changed (534 of
721).

The case `corpus/python/module_loaded_by_computed_name_returned` fails on revision 78.

MODEL_REVISION becomes `python-fastapi-dishka/79`.
