# ADR-0107: A getattr value with a known name dispatches by name

**Status:** Accepted, 2026-10-12; model revision 90.

ADR-0087 dispatches `getattr(value, "name")(...)` by name, as `value.name(...)`. Probing for an
optional hook keeps the value first:

```python
prime = getattr(tracker, "prime", None)
if prime:
    prime(items)
```

That form went through the path that localizes `getattr` values only for receivers of a known type,
and on a value of unknown type it protected nothing. In the blind eighth cohort three such optional
hooks of one project were reported, verdict false.

A `getattr` value with a constant or finite name on a value of unknown type that may not be a module
now dispatches by that name, as the attribute read `tracker.prime` does. An unknown name keeps the
previous handling.

The case `corpus/python/getattr_known_name_value` fails on revision 89.

MODEL_REVISION becomes `python-fastapi-dishka/90`.
