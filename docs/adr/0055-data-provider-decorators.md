# ADR-0055: Arguments of data-provider decorators are values, not fixtures

**Status:** Accepted, 2026-10-07; model revision 37.

A unittest method decorated with ddt's `@data`, `@idata`, or `@file_data`, or with
`parameterized.expand`, is called with arguments that the decorator generates. The tests world
read those parameters as pytest fixtures, found none, and marked the world incomplete (`DT3201`);
the effect was an incomplete tests world in many cohort projects, which suppresses findings there.

Parameters of a method that carries one of these decorators (listed in `DATA_PROVIDERS` in
`pytest_semantics.py`, matched through import expansion) are treated like `parametrize` names:
values, not fixture requests. `self` and `cls` are not parameters. Treating a name as a value
removes only an unresolved-fixture limitation; it adds no execution edge and reports nothing.

The case `corpus/frameworks/unittest_ddt_data` fails on revision 36 (the world is incomplete).

MODEL_REVISION becomes `python-fastapi-dishka/37`.
