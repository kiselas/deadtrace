# getattr with an unknown name on an unknown value

`dispatch` calls `getattr(obj, name)()` with a name and a value it receives. The project imports no
module by a computed name and keeps no module as a value, so `obj` is no project module: the
attribute is a member of a project class, or a value stored on the object, which escaped where it
was stored. `Plugin.handle` and `Plugin._audit` are protected by the call. `helper`, a module-level
function that nothing references, cannot be such an attribute and is a candidate.
