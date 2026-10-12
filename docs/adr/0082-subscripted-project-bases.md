# ADR-0082: A subscripted base is the project class it subscribes

**Status:** Accepted, 2026-10-12; model revision 65.

`class UserRepo(BaseRepo[User])` derives from the project class `BaseRepo`. The resolver looked up
each base expression as written, and a subscription is no name, so `BaseRepo[User]` resolved to
nothing and was recorded as an external base named `app.repo.BaseRepo`. Two things followed:

- An external base may call any method of a class by name, so every method of `UserRepo` was
  protected by an `external_base_hooks` guard, and its unused methods, and the unused methods of
  `BaseRepo`, were never reported.
- The MRO of `UserRepo` lacked `BaseRepo`, so inherited members, overrides, and the
  `__init_subclass__` of the base were not found through it. A test that defines
  `class _(BaseApi[Body])` inside `pytest.raises` to check the base's `__init_subclass__` had the
  class reported as unreached (four reviewed findings of one cohort project, verdict false).

A subscripted base now resolves through the subscribed expression, as `_base_name`, the hierarchy
of the blocking layer, and the computed-base rule already did. The class statement marks the
subscribed name as a base reference, not a value that escapes to an unknown consumer; the type
arguments are evaluated as before.

This removes guards, so it may add findings: unused methods of generic subclasses and bases.

The case `corpus/python/generic_project_base` fails on revision 64.

MODEL_REVISION becomes `python-fastapi-dishka/65`.
