# ADR-0060: Unittest cases in a test package `__init__.py` are collected

**Status:** Accepted, 2026-10-07; model revision 42.

Django's classic runner and `unittest discover` import a `tests` package and run the cases that
its `__init__.py` defines. The module name `__init__.py` matches no pytest pattern, so 142
reviewed members of one cohort project, whose cases live in `djangosaml2/tests/__init__.py`,
were reported as unreached.

ADR-0053 collects `test*.py` modules that define a unittest case. The same rule now also covers the
`__init__.py` of a package whose directory name starts with `test`. As in ADR-0053 the runner is
not known statically; collecting the module only keeps code and never reports it.

The case `corpus/frameworks/unittest_tests_package_init` fails on revision 41.

MODEL_REVISION becomes `python-fastapi-dishka/42`.
