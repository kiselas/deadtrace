# ADR-0025: Conventions found in installed libraries (model revision 18)

**Status:** Accepted, 2026-09-29.

## Context

The seventh field pass scanned code no earlier pass had seen: 39 installed packages, from a
migration tool to an async I/O library and a JSON Schema validator, staged as scan roots, after
projects that had not been scanned before (ADR-0024). Libraries are the hard case for a dead-code
analyzer, since callers are outside the project. Every finding was checked in the source, and each
false one was reproduced in a small project.

The packages had 88 findings before this change; 44 were false, of these kinds:

- an override of a public method in a private implementation class, called by users through the
  public base (`Process.terminate`, `TaskStatus.started`, `UNIXSocketStream.receive_fds`);
- module-level `__getattr__` and `__dir__` (PEP 562), 12 times in six packages;
- a class named only by a subscripted annotation, as `AwaitableOrContextManager[FormData]` or
  `type[_MiddlewareClass[P]]`;
- a method passed as a value, `partial(self.stream_response, send)` or `schedule(self.step)`,
  whose override in a subclass is what runs;
- a callback defined in each branch of a condition, of which only one definition was taken;
- `globals()["_render_%s_type" % name]`, a top-level function chosen by a computed name;
- test modules that create their tests when imported (`TestDraft3 = suite.to_unittest_testcase()`),
  which hold no `def test_` and were not run;
- a program with a main guard in a test directory, `tests/fuzz_validate.py`, that is neither a test
  file nor a library module;
- a class statement whose base is a value, `class Sub(validators.Draft7Validator)` with
  `Draft7Validator = create(...)`, or `class Boom(cls)` with `cls` a parameter, written for the
  `__init_subclass__` the base runs;
- `def cpu_count()` in one branch and `from os import cpu_count` in another;
- `request.getfixturevalue("_session_faker")` in a plugin's fixture.

## Decision

1. **Overrides of public methods.** In the automatic `library` world, a public method of an API
   class may be called on an instance of any project subclass. A boundary from the method reaches
   each subclass's override, gated by the subclass: it runs once the class may run in the world.
   An implementation that nothing constructs stays unreached.
2. **Module hooks.** A top-level `__getattr__` or `__dir__` runs when its module is reached, from
   attribute access and `dir()` on the module.
3. **Annotations.** A subscripted annotation names its class as well as its arguments:
   `Box[int]` uses `Box`. Variable types are unchanged: `Box[int]` still gives no type.
4. **Method references.** A method referenced as `self.method` and passed as an argument, to a
   project function that calls it or to a library, reaches the overrides of project subclasses as
   a call does. The same passing reaches every definition bound to a callback's name in branches.
5. **Computed names.** `globals()[name]` and `globals().get(name)` protect the top-level
   definitions of the module whose names have the constant start and end of `name`, or the named
   definition when it is a literal. The constant start and end of `"a_%s_b" % x` and
   `"a_{}_b".format(x)` are read like those of an f-string; that also narrows `import_module`.
6. **pytest.** A module that matches `python_files` is a root of the tests world whether or not it
   holds tests. `request.getfixturevalue("name")` with a literal name reaches the top-level
   definitions of that name, also in a plugin without tests.
7. **Scripts.** A module with a main guard, or named `__main__`, is a script root unless its file
   name is `test_*.py`, `*_test.py`, or `conftest.py`; a test directory does not make it a test.
8. **Class statements.** A class whose base is a parameter or local variable of the enclosing
   function, a module variable assigned from a call of a project function, or such a call itself
   (`class Sub(create(schema))`), is created for the effect of its base's hooks, like one with a
   project metaclass (ADR-0022). Other bases outside
   the project keep the earlier rules, so a model class deriving from `declarative_base()` is
   still reported when nothing uses it.
9. **Names bound by a definition and an import.** When an import from outside the project and a
   nested `def` bind the same name in a function, the call runs the definition.

`MODEL_REVISION` becomes `python-fastapi-dishka/18`. Configured worlds still replace the automatic
ones, so decision 1 applies to the `library` world only when no worlds are configured.

## Consequences

- The 44 false findings are gone. The 44 that remain were checked in the source: 22 in
  `alembic.testing`, a support package whose pytest plugin is loaded by configuration outside the
  sources; five private helpers of `alembic` and two of `pluggy` without a caller; four in `attr`
  that its sibling package `attrs`, which was not staged, uses; six in `dns`, socket methods of
  private backends and private helpers, reached only through a public module that re-exports
  them without being a package; and single unused private classes and helpers elsewhere, such as a
  `TypedDict` that only a local variable annotation names.
- The field projects of ADR-0022 to ADR-0024 report the same findings as before, except that two
  findings of `stf_access_manager` merge into one, since a dead function's return annotation
  `Page[Item]` now links it to `Page`.
- Corpus cases fail on revision 17: `python/override_reached_by_reference`,
  `generic_class_in_annotation`, `library_public_override`, `module_getattr_hook`,
  `branch_defined_callback`, `globals_lookup_by_name`, `script_in_tests_directory`,
  `class_from_computed_base`, `definition_or_import_fallback`, `fixture_requested_by_name`, and
  `frameworks/pytest_dynamic_test_module`.
- Not modeled: names re-exported by a public module that is no package (`dns.asyncbackend`), which
  the library rule reads only for packages; and a class value produced by `type(...)` or a
  metaclass call.
- The decision-1 boundaries add `DT2002` limitations to libraries whose API classes have
  subclasses, one per method with overrides.
