# ADR-0013: Django installed applications (model revision 10)

**Status:** Accepted, 2026-09-24.

## Context

Django loads much of a project by convention. A world rooted at `manage.py` already reached the
settings module through the `DJANGO_SETTINGS_MODULE` string, and the modules and classes the
settings name, such as `ROOT_URLCONF` and the `AppConfig` of an application, through ADR-0009's
strings rule. It did not reach what Django loads without a name: the `models` and `admin` modules
of installed applications, the model classes Django registers, management commands and the
`Command` class Django instantiates, template-tag libraries, or the module that
`WSGI_APPLICATION` names by an attribute. With automatic worlds, a Django project also counted as
a library, so its public names were roots and nothing was reported.

## Decision

1. **Settings.** A module that assigns `INSTALLED_APPS` at its top level is a Django settings
   module. Its installed applications are the strings in that assignment and in the lists it
   assigns to other `*_APPS` names, the usual way to split them.
2. **Applications.** An entry names a project package directly, or names an `AppConfig` class
   whose literal `name` gives the package, or else the package that contains the class. External
   applications, such as `django.contrib.admin`, add nothing.
3. **Autodiscovery.** The settings module has an import edge to each project application's
   package and to its `apps`, `models`, and `admin` modules, and to every module under its
   `templatetags` package and its `management.commands` package, except command modules whose
   names start with an underscore, which Django does not list. A command module constructs its
   `Command` class, and a `models` module, or a module of a `models` package, constructs each of
   its top-level classes, which Django registers.
4. **Worlds.** Without configured worlds, each settings module roots a `production:django` world,
   or `production:django:<module>` when there are several, with provenance
   `framework_application`. A Django project is an application, so the library world does not
   apply.
5. **Attributes named by strings.** A string `"pkg.mod.name"` that names no module or symbol, but
   whose prefix is a project module binding `name` at its top level, refers to that module, as
   `WSGI_APPLICATION = "mysite.wsgi.application"` does.

The capability is `django.installed-apps` (revision 1, modeled). Views, admin classes, template
filters, and signal receivers stay protected by the general rules: references passed to
`path`, external decorators, and the hooks of external base classes. `MODEL_REVISION` becomes
`python-fastapi-dishka/10`.

## Consequences

- The recorded case meets its expectations and moves to `corpus/frameworks/django_installed_apps`;
  `corpus/frameworks/django_automatic_worlds` holds the same project without configuration. The
  corpus holds 52 cases. `tests/test_django.py` checks one world per settings module, application
  lists and `AppConfig` names, that `*_APPS` lists alone are not settings, that only command
  modules Django lists construct their `Command`, and that a string naming an attribute a module
  does not bind refers to nothing.
- On a Django-shaped probe with middleware, context processors, signals, class-based views, an
  admin, a command, and a tag library, the automatic worlds report exactly its four dead
  functions.
- Alternating runs, fastest of three per side, `main` first and this change second (artifacts
  in `benchmarks/results/2026-09-24-django-installed-apps/`): the scale fixture 0.91 and 0.87
  seconds, the 50k service fixture 1.58 and 1.57, mypy 4.72 and 4.39, pygments 1.73 and 1.80,
  rich 0.64 and 0.63; peak RSS changes by at most 1 MiB.
- Migrations, fixtures, and the test runner's discovery are not modeled here; migrations keep the
  retention of the `django.migrations-runpython` capability.
