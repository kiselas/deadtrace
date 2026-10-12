# ADR-0088: An unknown attribute of an unknown value is a class member

**Status:** Accepted, 2026-10-12; model revision 71.

After ADR-0087, `getattr(value, name)(...)` still protected the whole graph when neither the
value's type nor the name is known. In the reviewed cohorts such calls (`getattr(client, func)(...)`,
`getattr(factory, method)(**kwargs)`) silenced whole projects: 73 of the 80 projects with this guard
reported nothing.

What can the attribute be? An attribute read on an object that is no module returns a member found
through its class, which is a project definition only if the class is a project class; a value
stored on the instance, which escaped where it was stored (ADR-0087); or an attribute of an object
outside the project, which is code outside the project or a project value handed to it, which
escaped there. A module's attribute can be any of its top-level definitions, so the question is
only whether the value may be a project module.

The value may be a project module when the project holds one as a value (ADR-0081, extended by
ADR-0087 to modules passed to calls, stored, or returned), or when it imports a module by a name it
computes: `import_module(path)`, `__import__(path)`, or `sys.modules[path]` with a path that is no
string constant (`sys.modules` however reached, `__import__("sys").modules` included). The
receiver itself may be a module by its form: `sys.modules[...]`, an
`import_module` result, a name bound to a project module or assigned one, or a parameter annotated
`ModuleType`.

So, for an unknown name on such a receiver:

- if the receiver may be a module by its form, or the project imports a module by a computed name,
  the whole-graph guard stays;
- otherwise the targets are every member of a project class, gated on that class (a method runs
  only on an instance or the class itself, which exist once the class is reached), and every
  top-level definition of a module held as a value, gated on that module.

This keeps the guard on classes reached in the world and frees module-level functions and classes
that nothing references. It supersedes the remaining part of ADR-0034's point 3 and the
test that a private module function stays protected under any unknown `getattr`; a module function
that nothing references cannot be attached to an object.

The case `corpus/python/getattr_unknown_name_member_universe` fails on revision 70.

MODEL_REVISION becomes `python-fastapi-dishka/71`.
