# ADR-0069: Dotted strings resolve through a nested package like imports

**Status:** Accepted, 2026-10-07; model revision 51.

A string that names a project module or object exactly is a reference (ADR-0017): Django's
`ROOT_URLCONF`, `DJANGO_SETTINGS_MODULE`, and `INSTALLED_APPS`, Celery's include lists, and similar
settings. A Django project kept in a subdirectory, such as `tests/library_app` run from `tests/`,
writes `ROOT_URLCONF = "library_app.urls"`; the module is `tests.library_app.urls`, so the string
named nothing and every view the URL configuration routes was reported as unreached (6 findings in
one cohort project, all false).

When a dotted string names nothing exactly and its first part is no top-level project name, the
shallowest unique project package with that last name (ADR-0065) takes its place and the string
is resolved again. A string only adds references.

The case `corpus/frameworks/django_nested_project_strings` fails on revision 50.

MODEL_REVISION becomes `python-fastapi-dishka/51`.
