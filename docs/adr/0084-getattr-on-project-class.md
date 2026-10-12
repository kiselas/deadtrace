# ADR-0084: getattr on a project class selects the class's members

**Status:** Accepted, 2026-10-12; model revision 67.

`getattr(receiver, name)` with a computed name selects members of the receiver's type by the
constant start and end of the name (ADR-0028, ADR-0034), when the receiver is a value of a known
project type. A receiver that is the class itself was not such a value:

```python
processor = getattr(Datasets, f"_process_{name}")
return processor(rows)
```

`Datasets` has no inferred instance type, so no member was selected. While a class handed to an
unknown consumer exposed every method, the class's private `_process_*` methods were protected by
that exposure; ADR-0083 removed it, and seven such methods of one cohort project were reported.

A receiver that resolves to a project class now selects the members of that class, its project
bases, and its subclasses, the same set a value of the class's type selects.

The case `corpus/python/getattr_on_class_computed_name` fails on revision 66.

MODEL_REVISION becomes `python-fastapi-dishka/67`.
