# ADR-0081: Modules held in a literal container dispatch by name

**Status:** Accepted, 2026-10-12; model revision 64.

A plugin table may hold modules rather than functions or classes:

```python
from .adapters import claude, codex, kimi

AGENT_LOADERS = {"claude-code": claude, "codex": codex, "kimi": kimi}

def _load_entries(agent_id):
    loader = AGENT_LOADERS.get(agent_id)
    return loader.load_entries() if loader else []
```

`loader` has no known type, so `loader.load_entries()` became a name dispatch over project methods
called `load_entries` (ADR-0009), and module-level functions of that name were not among them. Two
reviewed cohort projects (d and e) were reported this way: 18 members of RCH004 and two RCH001,
all verdict false.

The resolver now collects the project modules that a module imports and places as an element of
a literal dict, list, tuple, or set. A name called on a value of unknown type also dispatches to
the top-level definitions of that name in those modules, and a `getattr` with a constant name on
such a value selects them the same way. The rule needs both a module placed in a container and a
call of the same name on an unknown value; a module that is only imported keeps its unreached
definitions reported.

The case `corpus/python/module_dispatch_table` fails on revision 63.

MODEL_REVISION becomes `python-fastapi-dishka/64`.
