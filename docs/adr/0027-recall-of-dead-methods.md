# ADR-0027: Recall of dead methods (model revision 20)

**Status:** Accepted, 2026-09-29.

## Context

The first nine field passes looked for false findings: definitions reported as unused that
something uses. This pass asked the other question, whether dead code is found. Dead code was
injected into copies of six field projects: a function, a class, and a method of a class in twelve
modules, and one new method in each of forty classes. Names were unique, so a definition that no
finding held was a miss. The copies contained the analyzed sources and the small configuration
files, so the deployment rules of ADR-0023 applied.

Functions and classes were found in every project, apart from a plain Django class (below). Methods
of existing classes were not: 7 of 40 in one project, 12 in another, 2 in the Django and Celery
project. Following each miss to the rule that kept it showed five causes, each reproduced in a
small project:

- **A class that a binding builds.** `provide(Service)` registers the class as the factory of a
  binding, and a factory is a retained declaration. Everything defined inside a retained
  declaration was retained with it, and everything below a binding's factory was left out of
  `RCH001` in favour of `RCH003`. That is right for a binding that nothing requests, and wrong for
  the requested ones, which are almost all of them. Every method of a class in a Dishka
  application was protected.
- **An instance stored in a container.** `items.append(State())` passes an instance to a callee
  that is not resolved. Such a callee may call any method of the instance, so the class was handed
  to an unknown consumer with all its methods. A list, a set, and a dictionary keep what they
  receive.
- **An attribute read from a class.** `Table.id == value` and `Status.ACTIVE.value` name a class
  only for a field, a member of a base outside the project, or an enum member. The class was marked
  as used as a value, which exposes every method it has.
- **An implementation of an abstract method.** The subclass of a base that declares
  `@abstractmethod` has to define the method, or cannot be created, whether or not any call reaches
  it. Removing the method is not a cleanup.
- **A Django class without a base.** A plain helper class in `models.py` was kept because the
  module is registered, although Django loads models, which have a base.

## Decision

1. **Bindings.** Only the nodes below a factory that no demand reaches are left to `RCH003`; below a
   reached factory, an unreached definition is reported by `RCH001` like any other. A class that a
   binding registers keeps its retention as the factory, not its methods.
2. **Containers.** A call of `append`, `appendleft`, `add`, `extend`, `extendleft`, `insert`,
   `setdefault`, or `update` on a local, or on a `self` attribute, that is bound to a builtin
   container (a display, a comprehension, a call of `list`, `dict`, `set`, `deque`, `defaultdict`,
   or `OrderedDict`, or an annotation naming one) stores the arguments and calls nothing. The
   methods run where the value is read back, and a call there is resolved by the type or guarded by
   the name.
3. **Class attributes.** An attribute that does not resolve to a member of a class uses the class,
   not its methods. A callable or a module named the same way keeps its earlier behaviour.
4. **Abstract implementations.** A method of a class that implements an abstract method of a
   project base (`abstractmethod`, `abstractproperty`, `abstractclassmethod`, and
   `abstractstaticmethod`, by any import) is reached with the class, by a boundary of the domain
   `abstract_implementation`.
5. **Django models.** A class in a `models` module is registered only if it has a base.

Recall is measured by injection: `cycle10_inject.py` for functions and classes, and
`cycle10_inject_methods.py` for methods grouped by the kind of base. The scripts are not part of the
repository; the method is: the copy has unique names, and the report is read by name.

`MODEL_REVISION` becomes `python-fastapi-dishka/20`.

## Consequences

- Injected methods found, of 40 in each project: before the change, after it: 7 and 20 (a FastAPI service with Dishka), 20 and 20 (a
  service on `dependency_injector`), 2 and 2 (a Django REST framework project with Celery), 12 and
  17 (an agent with plugin classes), 35 and 37, 18 and 24.
- The remaining misses were followed to their causes. Most are classes with a base outside the
  project whose library calls methods by convention (Django REST framework serializers and views,
  Celery tasks, `dependency_injector` containers), and classes handed to a consumer that is not
  resolved. They are kept by design: the methods are hooks the analyzer cannot see, and a
  finding there would be a guess.
- The field projects report the same findings as before, with these differences, each checked in
  the source: three methods of service classes in two projects are new and unused (nothing
  calls them, nor a base or subclass of the name), and an implementation of an abstract method
  in one project is not reported any more. The installed packages of ADR-0025 and ADR-0026 gain
  three findings: two private methods of a proxy class in `redis` that nothing calls, and a
  `TypedDict` that only the annotation of a local variable names.
- Corpus cases fail on revision 19: `frameworks/dishka_requested_service_members`,
  `python/container_holds_instances`, `python/class_attribute_read`,
  `python/abstract_implementation_required`, and the extended
  `frameworks/django_framework_conventions`. Accepted.
