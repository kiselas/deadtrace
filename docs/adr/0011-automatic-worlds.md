# ADR-0011: Automatic worlds for scripts, applications, and libraries (model revision 8)

**Status:** Accepted, 2026-09-24.

## Context

Without configured worlds, only FastAPI applications and `pyproject.toml` entry points became
roots. Every other project fell back to one `production:application` world with the unresolvable
root `<auto>`, which `DT3001` made invalid, so scripts, Flask, Celery, and other applications, and
libraries got no findings at all. A FastAPI factory that only the server calls, as
`uvicorn main:create_app --factory` does, was not an application either, and a factory called from
another module was not recognized because its constructor was resolved in the caller's module.

The solver's default budget was a fixed 100,000 steps per world. A world visits each node at most
once per reachability kind, so a graph above 50,000 nodes could exhaust it and turn a complete
world into one that protects everything.

## Decision

Automatic worlds apply only when no world is configured.

1. **Scripts.** Modules named `__main__` and modules with a top-level
   `if __name__ == "__main__":`, in either operand order, are the roots of `production:scripts`,
   with provenance `main_module`. Test modules are skipped: files under `tests`, `test`, or
   `testing`, `test_*.py`, `*_test.py`, and `conftest.py`.
2. **Applications of frameworks without a capability.** A module-level object built by the
   application constructor of aiohttp, Bottle, Celery, Falcon, Flask, Litestar, Quart, Sanic,
   Starlette, or Typer makes its module a root; a top-level function that builds one, such as a
   Flask `create_app`, is a root itself. Each application gets a world named after its framework,
   or `framework:module.name` when the framework has several, with provenance
   `framework_application`. Handlers registered on the application by decorators are protected by
   the decorator rule of ADR-0008 (`frameworks.application-roots`, guarded).
3. **Uncalled FastAPI factories.** A top-level function that builds and returns a FastAPI
   application is an application of the web worlds even if no module calls it. Its constructor,
   lifespan, and dependencies resolve in the factory's own module (`fastapi.routes` revision 2).
4. **Celery autodiscovery.** `app.autodiscover_tasks()` at the top level of a Celery application's
   module may import every project module named `tasks`, or the given `related_name`; this is a
   `dynamic_import` boundary from that module (`celery.autodiscover-tasks`, guarded).
5. **Library.** When there is no application and no entry point, `production:library` roots the
   public API, with provenance `library_public_api`: every module whose dotted name has no part
   starting with an underscore, outside `tests`, `test`, `testing`, `docs`, `examples`, and
   `benchmarks`; its top-level names without a leading underscore; the names a literal `__all__`
   lists; for a package, the public names it imports, star imports included; and the public
   methods and nested classes of API classes. Callers reach names that `__all__` leaves out as
   attributes, so `__all__` only adds names.
6. **Fallback.** A project with none of these keeps the invalid `production:application` world.
7. **Step budget.** Without `max-steps`, the budget is twice the node count, which a world never
   exhausts; an explicit `max-steps` still caps the work.

`MODEL_REVISION` becomes `python-fastapi-dishka/8`. New capabilities: `python.script-roots` and
`python.library-roots`, modeled; `frameworks.application-roots` and `celery.autodiscover-tasks`,
guarded.

## Consequences

- Five corpus cases cover scripts and `__main__` modules, a library API, a Flask factory with a
  blueprint, Celery autodiscovery with a module outside it, and an uncalled FastAPI factory; the
  corpus holds 46. `tests/test_auto_worlds.py` pins the discovery rules and their limits, including
  that configured worlds replace every automatic one.
- On the staged sources, rich, pygments, pydantic, and mypy get complete library worlds, and scripts
  worlds where they have scripts, instead of an invalid world; `_pytest` is private by name and
  stays invalid. rich reports 16 members and pygments 4; five are dead code. The others show
  patterns the core model gets wrong, recorded as known violations in the same change: `@overload` stubs,
  IPython display hooks such as `_repr_mimebundle_`, a nested function bound in one branch and
  assigned in another, and a class passed to `ctypes`, which calls its `from_param`.
- Alternating runs, fastest of three per side, `main` first and this change second (artifacts
  in `benchmarks/results/2026-09-24-automatic-worlds/`): the scale fixture 0.72 and 0.76
  seconds, the 50k service fixture 1.67 and 1.88 (its framework stages differ by at most
  0.05 seconds), mypy 4.19 and 4.22, pygments 1.79 and 1.78, rich 0.65 and 0.65. Peak RSS grows
  by 12 to 18 MiB on the real packages, whose worlds are now solved instead of rejected. World
  planning had copied the root set once per root, which took 0.55 seconds with mypy's 5,503
  library roots; it now takes 0.02.
- A library world treats every public name as used, so it reports only private and unreachable
  code. Projects that want applications' precision configure their worlds.
- Default configurations get a new configuration digest, because `max-steps` is now unset rather
  than 100,000.
