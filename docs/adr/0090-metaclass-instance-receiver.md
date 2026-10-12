# ADR-0090: The first parameter of a metaclass method is a built class

**Status:** Accepted, 2026-10-12; model revision 73.

In a method of a metaclass, the first parameter is a class built with that metaclass, not an
instance of the metaclass's own members:

```python
class TypeMeta(type):
    @property
    def lookups(cls):
        return cls._lookups()

class BaseType(metaclass=TypeMeta):
    @staticmethod
    def _lookups(): ...
```

The model looked `_lookups` up in `TypeMeta`, found nothing, and the external base `type` left the
attribute unresolved. Until ADR-0083 the private-method exposure of the escaped classes hid it; in
the review of the findings revision 71 added, eight overrides of `_lookups` in one project were
reported, all verdict false.

A class is a metaclass when a base outside the project is `type`, `abc.ABCMeta`, `enum.EnumMeta`
or `enum.EnumType`, or ends in `Meta`. An attribute of the first parameter of its method that the
metaclass does not define now dispatches by name to every project member of that name, as an
attribute of a value of unknown type does (ADR-0009).

The case `corpus/python/metaclass_method_on_built_class` fails on revision 72.

MODEL_REVISION becomes `python-fastapi-dishka/73`.
