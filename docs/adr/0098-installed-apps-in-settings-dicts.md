# ADR-0098: INSTALLED_APPS in a settings dict installs applications

**Status:** Accepted, 2026-10-12; model revision 81.

ADR-0095 reads installed applications from `settings.configure(INSTALLED_APPS=[...])`. Test helpers
for reusable Django packages pass the same settings in other shapes, which a runner later hands to
`settings.configure`:

```python
HELPER_SETTINGS = dict(INSTALLED_APPS=["tests.media_app"], ...)      # djangocms-helper, app-helper
SETTINGS = {"INSTALLED_APPS": [...]}
@override_settings(INSTALLED_APPS=[...])
```

In the blind seventh cohort, two CMS plugins and models of such a test application were reported,
verdict false.

Any keyword argument `INSTALLED_APPS=` of a call, and any dict literal key `"INSTALLED_APPS"`, in a
module that is not a settings module now installs the applications it lists, as ADR-0095 does: the
edges start at that module, and it is no application of its own.

The case `corpus/frameworks/django_helper_settings_dict` fails on revision 80.

MODEL_REVISION becomes `python-fastapi-dishka/81`.
