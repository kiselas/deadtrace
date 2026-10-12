# ADR-0091: Modules imported inside functions can be values

**Status:** Accepted, 2026-10-12; model revision 74.

ADR-0081 and ADR-0087 treat a project module as a value when code places it in a container, passes
it to a call, stores it in an attribute, or returns it; a call on a value of unknown type then
dispatches by name to that module's top-level definitions. Only names that a module's top-level
imports bind were considered, so a module imported inside a function was missed:

```python
@pytest.fixture(scope="session")
def helpers():
    from tests.helpers import helpers
    return helpers

def test_build(helpers):
    helpers.dedent(...)
```

In the review of the findings revision 71 added, eight such helper functions of one project were
reported, all verdict false.

Imports inside functions and classes now bind names for this rule too, relative imports resolved
against the module's package. The rule is flow-insensitive within a module, as before: a local
name that some function binds to a project module counts wherever it is used as a value.

The case `corpus/frameworks/fixture_returns_module` fails on revision 73.

MODEL_REVISION becomes `python-fastapi-dishka/74`.
