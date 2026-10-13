# ADR-0108: Collected tests inherit usefixtures marks from project bases

**Status:** Accepted, 2026-10-13; model revision 91.

## Context

ADR-0016 reads usefixtures marks on a test method and its lexically enclosing classes.
Pytest also reads class marks through the MRO, as its get_unpacked_marks implementation
in _pytest/mark/structures.py specifies. A collected subclass may therefore request fixtures
named only on a base in another module. Two reviewed public findings were such live fixtures.

## Decision

For a collected test method, usefixtures requests also include decorator marks of its enclosing
classes' project ancestors. Resolve each decorator's pytest name in the module where that
decorator was written, so an alias such as `import pytest as pt` on a base remains recognized.
The fixture itself resolves in the consumer's existing fixture namespace. Edges remain local
to the tests world. Uncollected unrelated classes request no fixture through this rule.

Only usefixtures handling changes. General inheritance of parametrization and other marks is
outside this decision. No target code is imported or executed.

## Consequences

The independent case `corpus/frameworks/pytest_inherited_usefixtures` fails on revision 90
because `ready_for_case` is not test-live. It includes a base imported from another module under
a pytest alias, an intermediate subclass, two requested fixtures and an unused fixture
associated with an uncollected class. The unused fixture stays a candidate.

MODEL_REVISION becomes `python-fastapi-dishka/91`. Paired dev measurements and seed-7 injections
evaluate the field effect independently of the case; implementation alone is not a measured gain.
