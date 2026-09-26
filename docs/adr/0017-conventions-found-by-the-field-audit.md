# ADR-0017: Conventions found by the field audit (model revision 11)

**Status:** Accepted, 2026-09-26.

## Context

After ADR-0015 and ADR-0016, complete worlds on real projects produced findings for the first
time. Every finding on five private applications and on Deadtrace itself was checked against the
source. The false ones fell into classes that no synthetic case had covered; each was reduced to
a minimal rewritten case before the fix. No private source is recorded.

## Decision

Model revision `python-fastapi-dishka/11` adds these rules. Each adds possible execution only.

1. **Router includes.** An `include_router` call in a nested block, in a helper function that
   receives the application as a parameter (followed through up to three helper calls), or in a
   `for` loop over a literal list or tuple of routers, a concatenation of them, or a name bound
   once to one, is modeled when every application and router resolves. Any other
   `include_router` call is recorded as unknown, and then no router that code refers to beyond its
   own route decorators is reported as `RCH002`. A framework object imported through a package
   that re-exports it resolves to the object, not to the submodule of the same name.
2. **Entry points naming values.** A root such as `pkg.cli:app` that names a top-level value runs
   its module; when the value is a known application it is modeled, otherwise the world is partial
   with `DT3005`.
3. **Calls in annotations.** Calls inside parameter, return, and class-body annotations run as
   when the `def` or class runs, with or without `from __future__ import annotations`, since the
   framework that reads the signature evaluates them: `typer.Option(callback=...)`,
   `AfterValidator(...)`.
4. **Attribute chains.** In `Status.ACTIVE.value`, the longest prefix that is a project symbol is
   used even when the next part is not one.
5. **Nested option classes.** A nested class of a class with an external base that may call its
   methods is protected with them; a nested `Config` or `Meta` is protected under any external
   base, as Pydantic, Django, and Django REST framework read them.
6. **Django.** An installed application's `apps` module constructs its `AppConfig` subclasses; a
   settings module imports each module that calls `get_asgi_application` or
   `get_wsgi_application`, which a server loads; packages named by `MIGRATION_MODULES` are
   migrations. The `django.installed-apps` and `django.migrations-runpython` capabilities become
   revision 2.
7. **Alembic.** A module `env.py` that imports `alembic` is an external contract, and so are the
   modules of the `versions` directory beside it and their `upgrade`, `downgrade`,
   `upgrade_*`, and `downgrade_*` functions (`alembic.migrations`, revision 1).
8. **Dynamic modules.** Loading a module from a file path (`spec_from_file_location`,
   `SourceFileLoader`, `runpy.run_path`) may run any project module, and `runpy.run_module`
   imports by name like `import_module`. An attribute of a local bound to a module imported by a
   computed name may be any top-level definition of that name. `getattr` on a module imported
   from outside the project reaches no project code.
9. **Typed receivers.** A method called on a receiver typed as a `Protocol` may be any project
   method of that name, and one called on any typed receiver may also be a method of that name
   in test code, where hand-written stand-ins derive from nothing.
10. **Decorators.** pytest marks, `pytest.fixture`, and `pytest_asyncio.fixture` register
    nothing outside pytest, whose collection the tests world models; they no longer protect the
    decorated function as an external registration.
11. **Retention.** Definitions nested in a retained declaration are retained with it instead of
    being reported on their own.

`fastapi.routes` becomes revision 3 and `python.direct-flow` revision 6.

## Consequences

- Corpus cases `fastapi_router_registry`, `fastapi_unknown_include`,
  `django_framework_conventions`, `alembic_environment`, `annotation_metadata_calls`,
  `enum_member_attribute_chain`, and `pydantic_config_class` fail on the previous revision and
  pass on this one; the corpus holds 61 cases.
- On the audited projects the remaining findings were each confirmed as code that does not run
  under the analyzed inputs: 12 on a FastAPI and Dishka service of 108k lines, 16 and 15 on two
  smaller services, and dozens on two test-automation projects, most of them unused fixtures and
  helpers.
- When a scan reports little because unknown boundaries protect most code, the text report and
  `doctor` now name the widest guards with their locations, so the user can configure roots or
  keep contracts instead of seeing only a count.
