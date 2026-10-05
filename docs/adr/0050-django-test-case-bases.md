# ADR-0050: Django and DRF test case bases are unittest cases

**Status:** Accepted, 2026-10-06; model revision 32.

A held-out cohort of public GitHub projects (reviewed findings, `docs/field/`) showed that the
largest single class of false findings was test classes derived from `django.test.TestCase` and
its siblings: about 140 reviewed members in one project family were reported as unreached although
pytest collects and runs them. The tests world recognised `unittest.TestCase` and
`IsolatedAsyncioTestCase` bases only, so a class whose base is a library subclass of
`unittest.TestCase` was not a test.

Treat classes derived from `django.test.TestCase`, `SimpleTestCase`, `TransactionTestCase`,
`LiveServerTestCase`, `django.contrib.staticfiles.testing.StaticLiveServerTestCase`, and the Django
REST framework `APITestCase`, `APISimpleTestCase`, `APITransactionTestCase`, and
`APILiveServerTestCase` as unittest cases. The rule is a fixed list of documented classes that
derive from `unittest.TestCase`; it does not read installed packages (that is a separate decision)
and does not weaken any world. Matching is by the resolved dotted name of the base, as for the
existing bases, so an alias or a re-import resolves the same way.

Positive and negative controls are in `corpus/frameworks/pytest_django_test_case` (the test
classes are `not_candidate`, an uncalled function stays a candidate). The case fails on revision 31.
Other unittest-derived bases (for example Twisted's trial) are not added without their own case.

MODEL_REVISION becomes `python-fastapi-dishka/32`.
