# ADR-0059: Fixtures of the consumer's class take precedence

**Status:** Accepted, 2026-10-07; model revision 41.

pytest resolves a fixture request to the nearest definition: a fixture that a test's class (or
one of its bases) defines shadows a same-named fixture of another class, a module, or a
conftest. The tests world kept one fixture per name in a module namespace, so when two classes of
one module each defined `env`, only the last definition was visible and the other class's
fixture, with everything it calls, was reported as unreached (10 reviewed members in one
cohort project).

For a consumer that is a method, the fixtures owned by its class and its project ancestors are
laid over the visible namespace, nearest class last. Fixtures requested by a class-owned fixture
resolve the same way. A request that previously resolved to another class's fixture now resolves
to the consumer's own; every fixture still has its definition reached by the tests that request it.

The case `corpus/frameworks/class_scoped_fixture_same_name` fails on revision 40.

MODEL_REVISION becomes `python-fastapi-dishka/41`.
