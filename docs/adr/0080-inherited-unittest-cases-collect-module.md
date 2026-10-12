# ADR-0080: A module whose cases inherit TestCase through a project base is collected

**Status:** Accepted, 2026-10-12; model revision 63.

ADR-0053 collects `test*.py` modules that define a unittest case, and ADR-0060 extends it to the
`__init__.py` of a `test*` package. Both looked only at the direct bases of a class. A Django
sample app that reruns a shared suite subclasses the suite's classes, which a module elsewhere
derives from `TestCase`:

```python
from openwisp_users.tests.test_admin import TestUsersAdmin as BaseTestUsersAdmin


class TestUsersAdmin(BaseTestUsersAdmin):
    app_label = "sample_users"
```

The direct base is a project class, so the module was not collected and 13 classes of one
reviewed cohort project were reported as unreached (cohort e, verdict false).

The rule now asks whether any class of the module's project ancestry is a unittest case, the same
question `_collected_classes` already asks for the classes of a collected module. As before, the
runner is not known statically; collecting the module only keeps code and never reports it.

The case `corpus/frameworks/unittest_inherited_case_module` fails on revision 62.

MODEL_REVISION becomes `python-fastapi-dishka/63`.
