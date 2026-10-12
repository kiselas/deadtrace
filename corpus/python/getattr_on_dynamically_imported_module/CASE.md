# getattr on a module imported by a computed name

`load` imports a validator module by a name built from its arguments and returns
`getattr(mod, kind)`, which the caller invokes. Both the module and the attribute name come from
data, so any public top-level definition of a project module may be returned: `validate_api` is
protected. `_never` is private, which no name read from data selects, and is called by nothing.
