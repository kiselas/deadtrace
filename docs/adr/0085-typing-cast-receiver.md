# ADR-0085: typing.cast names the type of its result

**Status:** Accepted, 2026-10-12; model revision 68.

`typing.cast(T, value)` returns `value` unchanged; code casts to call a member of `T` on a value
whose static type is wider:

```python
return cast(ArchiveStrategy, self.archive)._build_archive_strategy()
```

The call of a function outside the project returned a value outside the project, so
`_build_archive_strategy` had no caller. A class handed to an unknown consumer exposed its private
methods until ADR-0083, which hid the gap; after it, a reviewed cohort project reported the method.

A call of `typing.cast` or `typing_extensions.cast` now has the type that its first argument names
when that is one project class, a string annotation included, as a return annotation would give
it. A union or a class outside the project gives no type, as before. This only adds edges.

The case `corpus/python/typing_cast_receiver` fails on revision 67.

MODEL_REVISION becomes `python-fastapi-dishka/68`.
