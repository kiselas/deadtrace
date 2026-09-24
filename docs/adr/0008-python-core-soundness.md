# ADR-0008: Python-core soundness rules (model revision 5)

**Status:** Accepted, 2026-09-24.

## Context

ADR-0006 recorded thirteen cases in which a complete world, with no limitation, reported code that
may run as an unreached candidate: functions stored in a registry or returned as values, callables
handed to a project function, base classes and inherited methods, a base initializer called through
`super()`, an override called through a base-class annotation, a method on the result of an
unannotated factory, the class of a called static method, a class named only in an evaluated
annotation, a project decorator applied without parentheses, and functions registered by decorators
of frameworks Deadtrace does not model (Celery, click). The model only followed calls whose callee
resolved to a symbol, and it had no notion of classes beyond their names.

While fixing them, two resolver errors surfaced: a bare name in a method resolved to a sibling
method, although class scopes are not visible from the functions inside them, and parameters and
local variables did not shadow project symbols of the same name.

## Decision

The Python frontend adds these rules. Each one either adds a resolved edge where the target is
known, or a conservative boundary where only a set of possible targets is known.

1. **References.** A project function or class used as a value — stored, returned, passed to a
   project function that does not call it, or reached through an attribute such as
   `task.delay` — escapes. The scope that holds the reference gets one `escaped_reference`
   boundary covering every such target it does not already reach through an edge. Arguments of
   calls into unresolved consumers keep their `escaped_callable` boundary, which framework
   capabilities can account for.
2. **Members and owners.** A reached member reaches its owner (`member` edge), so the class of a
   called static method and the function that defines a closure are used.
3. **Bases.** A class reaches its project base classes (`inherit` edge). Attribute lookup on a
   class or on an instance of known type follows the C3 method resolution order over project
   classes; `super().name` looks past the containing class; constructing a class reaches the
   initializer that lookup finds.
4. **Dispatch.** A method called through an instance of known type also reaches the overrides of
   that method in project subclasses (class hierarchy analysis). Calls through the class itself or
   through `super()` do not dispatch.
5. **Unknown receivers.** A method looked up on a value whose type is neither a project class nor
   outside the project may be any project method of that name. The scope gets one
   `unresolved_method_dispatch` boundary listing those methods. Values of external types (imported
   packages, results of their calls, literals, and parameters annotated with external types) do not
   produce it.
6. **Decorators.** Applying a project decorator calls it; the decorated function is linked by a
   callback edge when the decorator calls its first parameter, and escapes otherwise. A decorator
   from outside the project registers the decorated function (`decorator_registration`), unless it
   is one of a short list of transparent standard decorators (`staticmethod`, `functools.wraps`,
   `dataclasses.dataclass`, `typing.overload`, and similar). Framework capabilities remove the
   boundary for registrations they model exactly: routes, hooks, provider factories, and Pydantic
   hooks. Nested definitions have their decorators and defaults evaluated where they are defined.
7. **Annotations.** Parameter and return annotations of a function, and annotations in class and
   module bodies, are evaluated at runtime; the classes they name are reached (`annotation` edge).
   Annotations of local variables are not evaluated and do not count.
8. **Scoping.** Names resolve in Python's order: the current function's nested definitions and
   those of enclosing functions, then the module. Class scopes are visible only to the class body.
   A name the function binds (parameters, assignment, loop, `with`, `except`, and import targets,
   `match` captures) shadows project symbols of the same name.
9. **Pydantic.** Validator, serializer, and schema hooks run whenever their model is used, not only
   when a route declares the model.

`MODEL_REVISION` becomes `python-fastapi-dishka/5`; `python.direct-flow` and `pydantic.hooks` move
to revision 2. `EdgeKind` gains `member`, `inherit`, and `annotation`; finding construction ignores
`member` edges when collecting a binding's component, because ownership is already an adjacency.

## Consequences

- All thirteen known-violation cases meet their expectations and moved to `corpus/`, which now holds
  31 cases. Each Python-core case keeps its control candidate, so none is satisfied by weakening the
  world. `tests/test_python_soundness.py` checks that every rule stays local: a reference in dead
  code, an unrelated hierarchy, a transparent decorator, an unreached module, a shadowing parameter,
  a sibling method name, and an annotation of a dead function protect nothing.
- On the audit probes, a FastAPI project went from ten findings with seven false to two true ones,
  and a plain script from six findings with five false to one true one. The 50k service fixture
  still reports exactly its 178 unused functions.
- `Service` in `dishka_conditional` and `dishka_inactive_injection` is now live: the endpoint's
  evaluated annotation `FromDishka[Service]` uses it. The Dishka guard still covers the binding.
- Reports contain more `DT2002` limitations, one per scope that crosses a conservative boundary.
- The frontend does more work per node; the measured cost is in
  `benchmarks/results/2026-09-24-python-core-soundness.md`.
- Unknown-receiver dispatch trades findings for safety: a method whose name is also used on values
  of unknown type is no longer a candidate. Better type inference narrows it.
