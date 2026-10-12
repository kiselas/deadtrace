# ADR-0103: getattr on a dynamically imported module

**Status:** Accepted, 2026-10-12; model revision 86.

`module = import_module(name)` followed by `module.check` already reaches the `check` of any module
(ADR-0017). Reading the attribute by `getattr` and keeping the value was not covered:

```python
mod = __import__(f"{path}.{module_name}", fromlist=[kind])
klass = getattr(mod, kind)
return klass
```

A validator function loaded this way in one reviewed cohort project was reported, verdict false.

`getattr(module, name)` on a local bound to a module that the scope imports by a computed name now
uses the top-level definitions of every project module named `name` when the name is a known string,
and every public top-level definition when it is not: a name read from data does not select a
private definition, as ADR-0092 assumes for listings. The recall injections did not change.

The case `corpus/python/getattr_on_dynamically_imported_module` fails on revision 85.

MODEL_REVISION becomes `python-fastapi-dishka/86`.
