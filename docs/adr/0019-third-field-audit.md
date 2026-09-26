# ADR-0019: Third field audit: factories, plugins, and build copies (model revision 13)

**Status:** Accepted, 2026-09-26.

## Context

The third pass re-ran every audited project and three more, checked determinism and the
performance fixtures, and exercised the CI workflow (`explain`, baselines, `compare`) on a real
report. Reports were byte-identical across runs. The false findings left had four causes.

- **An application factory that returns a wrapper.** A FastAPI and Socket.IO game built its
  application inside `create_application()` and returned it wrapped in an ASGI application;
  `uvicorn app.main:create_default --factory` ran `create_default`, which nothing in the project
  called. No web world was found, the project counted as a library, and nothing was reported.
- **Imports of a package's own submodules.** ADR-0015 refused to resolve an absolute import to
  the importer itself or to a package containing it, to keep `celery.py` from importing itself.
  That also refused `from app.handlers import poll` in `app/handlers/__init__.py` and in its
  siblings, so every command handler of the game was reported: 61 findings, 57 of them false.
- **pytest plugins as libraries.** A pytest plugin with a `pytest11` entry point is a library
  that its users' tests import, so its public API, including the objects its fixtures hand out,
  is used from outside the project. It had no library world because it had entry points.
- **Build copies and nested test classes.** `build/lib` held a setuptools copy of the package, so
  every class existed twice and the copy was reported; pytest collects `Test*` classes nested
  in collected classes, which were reported as unreached.

A monorepo showed that `import_module(x.__module__)` and similar calls are harmless, handled by
ADR-0018. The service fixture of PERF-00 ran about 25% slower on this branch: the typed-receiver
rule of ADR-0017 checked every same-named method's path; it now uses the cached index of test
code, and the branch is no slower than `main` under a profiler.

## Decision

1. **Wrapped factories.** A top-level function outside test code that constructs exactly one
   FastAPI application in a local is an application factory even when it returns something
   else. A top-level function that calls such a factory and that no project code calls is a
   root of the application's world, as a server runs it by name.
2. **Own submodules.** An absolute import resolves against a directory of the importer that is
   no regular package unless the importer is a module, not a package, of exactly that name.
3. **Plugin libraries.** A project with a `pytest11` entry point also gets a library world whose
   roots are the public API of the plugin's top-level package only. The public methods of the
   project classes a plugin fixture's return annotation names are roots of the plugin's world.
4. **Build copies.** Discovery skips a `build` directory that holds a setuptools `lib`, `lib.*`,
   or `bdist.*` directory (ADR-0015's rule for environments).
5. **Nested test classes** matching `python_classes` inside a collected class are collected.

`MODEL_REVISION` becomes `python-fastapi-dishka/13`.

## Consequences

- The game reports four findings, each confirmed; `corpus/frameworks/fastapi_wrapped_factory`
  records the wrapper pattern and fails on the previous revision, and
  `tests/test_import_roots_and_dispatch.py` records the submodule imports.
- The two pytest plugin projects report 52 and 18 findings instead of 71 and 59; the difference
  is their packages' public API, which their users may call.
- Fingerprints include the worlds of a finding, so a change of worlds, such as a new
  application, renews every fingerprint and a baseline reports them as new. Comparison
  correlates such changed groups; stable fingerprints across world changes are open work.
