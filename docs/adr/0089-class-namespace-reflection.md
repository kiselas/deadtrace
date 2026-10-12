# ADR-0089: Reflection over a namespace uses its members

**Status:** Accepted, 2026-10-12; model revision 72.

Two reflective forms reached members without a call the model resolved, and private-method
exposure (removed by ADR-0083) had hidden them:

```python
handler = type(self).__dict__.get("_On" + node.op_type)   # an entry of a class namespace
[name for name in dir(obj) if inspect.ismethod(getattr(obj, name))]   # a listing
```

In the review of the findings that revision 71 added (cohorts b-f, 99 findings), five methods of
one project were reached the first way and three test services the second, all verdict false.

- `x.__dict__.get(name)` and `vars(x).get(name)` read one attribute of `x` and are modeled as
  `getattr(x, name)` (ADR-0022, ADR-0028, ADR-0087, ADR-0088).
- `dir(x)`, `vars(x)`, `inspect.getmembers(x)` and `inspect.getmembers_static(x)` list the members
  of `x`, which code then uses by the listed names. A value of known project type, or a project
  class, lists the members of its class family; a value of unknown type lists the members of
  project classes, gated on their classes, as ADR-0088 does for an unknown name. A value that may
  be a module, a module outside the project, or a project importing modules by computed names
  keeps the current handling.

This only adds protection; it may remove findings.

The case `corpus/python/class_namespace_reflection` fails on revision 71.

MODEL_REVISION becomes `python-fastapi-dishka/72`.
