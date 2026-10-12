# ADR-0102: A class statement expected to raise is used

**Status:** Accepted, 2026-10-12; model revision 85.

Tests of class-construction checks declare a class inside a block that expects an error:

```python
with pytest.raises(ApiSetupError):

    class _(BaseApi[Body]):
        url = "https://example.com"
```

The class is never referenced; running its statement is the behaviour under test. When the base's
hook is not a project class (an external base, a metaclass the model does not follow, a
descriptor's `__set_name__`), nothing reached the class, and it was reported. Six findings of four
reviewed projects were such classes, verdict false.

A class statement in the block of a `with` whose context manager is a call named `raises`,
`warns`, `assertRaises`, `assertRaisesRegex`, `assertWarns` or `assertWarnsRegex` is now used by the
code that runs the block. Nested function bodies in the block are not searched.

The case `corpus/frameworks/class_statement_expected_to_raise` fails on revision 84.

MODEL_REVISION becomes `python-fastapi-dishka/85`.
