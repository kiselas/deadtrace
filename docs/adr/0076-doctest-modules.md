# ADR-0076: Docstring examples under `--doctest-modules`

**Status:** Accepted, 2026-10-12; model revision 58.

With `--doctest-modules` in `addopts`, pytest imports every module and runs the `>>>` examples of
its docstrings. A function that only those examples call was reported as unreached (5 reviewed
findings in one cohort project, scientific libraries use this heavily).

When the pytest configuration's `addopts` contains `--doctest-modules`, docstrings of modules,
classes and functions are parsed with the standard library's `doctest.DocTestParser`, which reads
text and runs nothing; each example is parsed with `ast`, and a plain name or a `module.name`
through the module's imports that resolves to a project definition becomes a root of the tests
world. As with other test roots, production code reached only this way is an RCH004 finding.

Revision 62: imports written in the examples themselves (`>>> from tests.examples import Plan`) bind
names for the examples that follow, and the imported definitions are reached too.

The case `corpus/frameworks/pytest_doctest_modules` fails on revision 57 (and its `sample_basket`
target on revision 61).

MODEL_REVISION becomes `python-fastapi-dishka/58`.
