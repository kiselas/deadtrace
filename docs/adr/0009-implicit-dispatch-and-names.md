# ADR-0009: Implicit dispatch, external base hooks, and modules named by strings (model revision 6)

**Status:** Accepted, 2026-09-24.

## Context

After ADR-0008, a third probe found complete worlds reporting code that the Python runtime or an
external library calls without the project naming it: `__str__`, `__eq__`, and `__hash__` used by
printing, comparison, and hashing; a dataclass's `__post_init__`; `visit_Call` on an
`ast.NodeVisitor`, `run` on a `threading.Thread`, and `emit` on a `logging.Handler`; and the top level
of modules imported with `importlib.import_module`, by literal and by f-string. Framework code works
the same way: Django calls `save` and `clean` on models, unittest calls `setUp`, Celery calls `run` on
task classes. The earlier protection covered only twenty named protocol methods.

The solver also added a `DT2002` limitation for every boundary it crossed, even when every target was
already resolved, which made reports noisy without telling the reader anything.

## Decision

1. **Special methods.** Every `__name__` method of a class is protected conservatively when the class
   is used, since Python and libraries call such methods implicitly. This replaces the list of twenty.
2. **External base hooks.** When a class, or a project class in its method resolution order, has a
   base that is not a project class, the methods it defines are protected conservatively once it is
   used, because the external base may call them by name. Bases known to call nothing beyond special
   methods and capability-modeled hooks are exempt: builtins and builtin exceptions, `object`,
   `abc.ABC`, the `typing` and `typing_extensions` `Generic`, `Protocol`, `NamedTuple`, and
   `TypedDict`, `pydantic.BaseModel`, and `dishka.Provider`. For `enum` bases only `_missing_` and
   `_generate_next_value_` are protected.
3. **Names in strings.** A string constant that exactly equals a project module name or a symbol's
   full name, as `"pkg.mod"`, `"pkg.mod.name"`, or `"pkg.mod:name"`, is a reference to it. Only strings
   containing a dot or a colon are considered. This covers settings lists, `include("app.urls")`, and
   similar registries.
4. **Dynamic imports.** `importlib.import_module`, `importlib.__import__`, and `__import__` with a
   literal name reach that module; with an f-string they may import any project module whose name
   starts with its literal prefix; otherwise any project module. Reaching a module conservatively runs
   its top level.
5. **`DT2002` only when protective.** After a world's fixpoint, a crossed boundary yields `DT2002` only
   if at least one of its targets is reachable conservatively and not resolved, or if it has no
   targets and therefore protects the whole graph. The check runs after the fixpoint, so it does not
   depend on traversal order.

`MODEL_REVISION` becomes `python-fastapi-dishka/6`; `python.direct-flow` moves to revision 3.

## Consequences

- Four new cases met their expectations and moved to `corpus/`, which now holds 35. Their control
  candidates are still reported, including a module outside the imported prefix.
  `tests/test_python_soundness.py` adds checks that exempt bases, unused subclasses of external
  classes, and strings in dead code or with extra text protect nothing.
- On the third probe, nine findings with eight false became one true one; the earlier probes and the
  50k service fixture are unchanged.
- `dishka_inactive_injection` no longer lists `DT2002`: its guard protects only the demanded type,
  which the endpoint's annotation already makes live.
- Alternating runs show no measurable cost: mypy 5.96 s on `main` against 5.44 s, the 50k service
  fixture 1.93 against 1.92 (host loaded; see `benchmarks/results/2026-09-24-implicit-dispatch/`).
- Methods of classes with an external base that is not on the exempt list are no longer reported
  when their class is used. A framework capability can narrow that by naming the hooks it knows.
