# Reflection over a class namespace

`Context.calculate` reads `type(self).__dict__.get("_On" + op)` and calls the entry, which is
`getattr(type(self), "_On" + op)`: `_OnConstant` fits the name and is protected. `describe` lists the
members of a value it receives with `inspect.getmembers` and hands them on; the value has no known
type, so the members of project classes, `Service.ping` among them, are protected. The module
function `_unused` is neither listed nor named.
