# ADR-0095: settings.configure installs Django applications

**Status:** Accepted, 2026-10-12; model revision 78.

Django imports the modules of installed applications and registers their models (ADR-0017 and
later). Installed applications were read only from a settings module, one that assigns
`INSTALLED_APPS` at its top level. Reusable Django packages commonly test themselves without one:

```python
def pytest_configure():
    from django.conf import settings
    settings.configure(INSTALLED_APPS=["django.contrib.contenttypes", "tests"], ...)
```

In the blind seventh cohort, models of such a test application were reported (verdicts split:
five false, three true, the latter with no other reference than the registry).

A call of `settings.configure` (as `django.conf.settings`) now installs the applications listed in
its `INSTALLED_APPS` and other `*_APPS` keyword arguments: Django imports their packages, `apps`,
`models`, `admin`, command and template-tag modules, and registers the models, as from a settings
module. The calling module is not an application of its own, so no application world or server
module is added for it; the edges start at the calling module, which in a conftest runs in the tests
world.

The case `corpus/frameworks/django_settings_configure_in_conftest` fails on revision 77.

MODEL_REVISION becomes `python-fastapi-dishka/78`.
