# ADR-0094: Annotations in a class body see the enclosing function's classes

**Status:** Accepted, 2026-10-12; model revision 77.

A class body evaluates its field annotations when the class statement runs, and a bare name there
resolves in the class body, then in enclosing function scopes, then in the module. The model looked
only in the class itself and in the module, so a class defined beside it inside the same function
was not found:

```python
def test_hydrate():
    @dataclass
    class Pet:
        name: str

    @dataclass
    class Person:
        pets: list[Pet]

    make_schema(Person)
```

In the blind seventh cohort, six findings of three projects were such local classes (`Pet` above,
`C` in `Dict[bytes, C]`), all verdict false.

The annotation name is now also looked up in each enclosing definition, innermost first, before the
module. The look-up also passes through enclosing class bodies, which Python skips; it can only add
references.

The case `corpus/python/local_class_in_sibling_annotation` fails on revision 76.

MODEL_REVISION becomes `python-fastapi-dishka/77`.
