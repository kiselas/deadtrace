# ADR-0026: More conventions found in installed packages (model revision 19)

**Status:** Accepted, 2026-09-29.

## Context

The eighth field pass scanned 57 more installed packages, from the Django ecosystem (Django itself,
Django REST framework, `drf_spectacular`, `django_celery_beat`) and the Celery stack (`celery`,
`kombu`, `billiard`) to `sentry_sdk`, `aiohttp`, `tornado`, `redis`, `typer`, `dishka`, `pydantic`,
`mypy`, and the pytest plugins of Playwright and Django. The packages had 86 findings before this
change. Every finding was checked in the source; 29 were false, of these kinds, each reproduced in
a small project:

- **The API of a library with a command line.** `typer/__init__.py` re-exports `getchar`, `run`,
  `progressbar`, `CallbackParam` and others with `from ._click.termui import getchar as getchar`.
  The package holds a Typer application, so it had no `library` world and the API was reported.
- **Quoted annotations.** `def collect(o: "Options") -> "Behaviour"` names its classes as the
  unquoted form does, but the analyzer read only names, so the TypedDicts of a typed library that
  quotes every annotation (`sentry_sdk._types`) were reported: 12 findings.
- **`locals()` as a value.** `def label(): def fget(self): ...; def fset(self, v): ...; return
  locals()` followed by `label = property(**label())` builds a property from nested functions.
- **A mixin that calls a member of its subclass.** `GraphCommands.commit` calls
  `self._build_params_header(...)`, which `Graph(GraphCommands)` defines.
- **A stand-in for a member a base provides.** `Service(gateways: Gateways)` calls
  `gateways.mikrotik()`, where `Gateways` is a container whose base supplies `mikrotik` as an
  attribute; the test passes a `_GatewaysStub` with a `mikrotik` method. This was reported before
  for unquoted annotations, and appeared for the quoted ones once they gave a type.

## Decision

1. **Package exports.** When a project has applications, the names that a top-level package's
   `__init__.py` re-exports explicitly (`import y as y`, `from m import y as y`) or lists in
   `__all__`, with the public methods of exported classes, are roots of the world
   `production:exports`. It is not the whole `library` rule: the other public modules of the
   package are not roots, so the dead code of an application that has such an `__init__` is still
   reported.
2. **Quoted annotations.** A string that is a whole annotation, or an element of a subscript, is
   parsed as an expression (up to 200 characters) and gives the names it holds. The strings of a
   `Literal` are values and give none.
3. **Nested definitions and `locals()`.** A call of `locals()` or `vars()` with no arguments in a
   function makes the function's nested definitions escape.
4. **`self` members the class lacks.** `self.name` or `cls.name` where neither the class nor its
   bases define `name`, and the class has no base outside the project, reaches the members named
   `name` of the project's subclasses of the class and of the other bases of those subclasses.
5. **Members missing on a typed receiver.** `value.name`, called or referenced, where `value` is
   known to be an instance of a project class that has no member `name`, reaches the project
   subclasses' members of that name and the methods of that name in test code, as a call through
   a base-class annotation does (ADR-0008, ADR-0018). `self` and `cls` are left out: which subclass
   a call on them meets is the question of ADR-0020, and this rule would reach every subclass.

`MODEL_REVISION` becomes `python-fastapi-dishka/19`.

## Consequences

- The 29 false findings are gone and 57 remain; the remaining ones were checked and are unused
  private helpers, vendored modules (`dishka._adaptix`), functions of a private module that the
  package's sibling distributions use, and type-only classes that only annotations of local
  variables name.
- The field projects of ADR-0022 to ADR-0025 report the same findings as before.
- Corpus cases fail on revision 18: `frameworks/package_exports_next_to_application`,
  `python/quoted_annotation_classes`, `property_from_locals`, `mixin_calls_subclass_method`,
  and `stand_in_for_provided_member`.
- Not modeled: code that only a pytest plugin, or a tool, registered by an entry point in package
  metadata calls, since metadata is not part of the sources; the plugin packages of Django and
  Playwright report their hooks and fixtures for that reason.
