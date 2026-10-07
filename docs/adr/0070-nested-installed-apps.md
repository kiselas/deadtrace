# ADR-0070: Installed applications resolve through a nested package

**Status:** Accepted, 2026-10-07; model revision 52.

ADR-0069 resolves dotted strings through the unique nested package. Django's installed
applications are read separately (`_django_app_package`), and matched project packages only by
exact name, so `INSTALLED_APPS = ["date_views"]` in `example/project/settings.py` did not reach
`example/date_views`: its `admin` and `models` modules were never imported and its `ModelAdmin`
classes and models were reported as unreached (reviewed findings in two cohort projects).

An installed application that names no project module exactly is looked up through the same
unique nested package before its `AppConfig` is resolved. The rule only adds imports.

The case `corpus/frameworks/django_nested_project_strings` (its `blog` application) fails on
revision 51.

MODEL_REVISION becomes `python-fastapi-dishka/52`.
