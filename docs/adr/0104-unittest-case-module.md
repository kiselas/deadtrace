# ADR-0104: TestCase imported from unittest.case

**Status:** Accepted, 2026-10-12; model revision 87.

pytest collects subclasses of `unittest.TestCase` whatever their names (ADR-0050). The model
recognized the base by its expanded name ending in `unittest.TestCase`, so
`from unittest.case import TestCase`, the module that defines the class, expanded to
`unittest.case.TestCase` and was not recognized. In one reviewed project two whole test classes, and
the fixtures only they used, were taken for uncollected code.

`unittest.case.TestCase` now counts as the unittest base, in test collection and for the classes
`unittest.main()` runs.

The case `corpus/frameworks/unittest_case_module_import` fails on revision 86.

MODEL_REVISION becomes `python-fastapi-dishka/87`.
