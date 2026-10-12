# ADR-0100: An instance stored on an unknown object is handed on

**Status:** Accepted, 2026-10-12; model revision 83.

A project instance passed to code outside the project offers that code its public methods (ADR-0017,
ADR-0083). Storing the instance as an attribute of an object that such code owns hands it on the
same way:

```python
request = RequestFactory().get("/")
request.user = MockSuperUser()
admin_view(request)  # Django calls request.user.has_perm(...)
```

The model did not treat the store as a hand-over, so the stand-in's methods were reported; in the
reviewed cohorts six findings of four projects were such protocol stand-ins, verdict false.

An assignment `obj.attr = value` now exposes the class of `value`, when it is a project class, as a
consumer would: its public methods, special methods and `_name_` hooks may run. It applies when
`obj` is not `self` or `cls`, not a value of a project type the model follows, and not a project
module or class. The recall injections did not change (534 of 721).

The case `corpus/python/instance_stored_on_unknown_object` fails on revision 82.

MODEL_REVISION becomes `python-fastapi-dishka/83`.
