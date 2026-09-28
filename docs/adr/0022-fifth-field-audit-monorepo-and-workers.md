# ADR-0022: Fifth field audit: a monorepo, workers, and pytest sessions (model revision 15)

**Status:** Accepted, 2026-09-28.

## Context

The fifth pass scanned a 624k-line monorepo of twelve FastAPI services with shared libraries,
FastStream, taskiq, and arq workers, Alembic migrations, and a pytest suite per service, besides
the projects of the earlier passes and the older revisions used for ADR-0021. On `main` the
monorepo reported nothing: every production world was complete, but almost every definition was
kept by conservative guards, and the tests world was partial. Random samples of 160 findings
were then checked against the source after each round of fixes, first by reading and then by
independent reviewers; each false finding below was reproduced in a minimal project.

Imports and worlds:

- Each service is a directory without `__init__.py` holding a package of its name, so
  `shop/shop/main.py` runs `from shop.routes import router`. The first part named the root
  directory `shop/`, so the import did not resolve; a two-service
  reproduction reported an included router (`RCH002`) and a called helper. Some service packages
  have no `__init__.py` either, and libraries in `libs/common/common` are imported as `common`
  from editable installs. `from alembic import context` in `svc/svc/alembic/env.py` resolved to
  the migration directory beside it, so the environment was not recognized.
- Alembic and Django migrations were conservative roots of every production world, so each
  application of the monorepo ran every service's migrations and what they import.
- FastStream applications, taskiq schedulers, and arq workers are started by their own commands;
  no world rooted them, so their subscribers, hooks, and tasks were reported, or reported as
  reached only from tests (`RCH004`).

Dispatch:

- A call on a value of unknown type protects every method of that name in the project; in a
  monorepo it reached every service's classes. `importlib.import_module(f"{obj.__module__}.tables")`
  protected every module, as did a computed name whose constant parts are only a suffix.
- A field annotated `self.proxy: PlainProxy | SlugProxy` took the first class of the
  union, as did a parameter so annotated, and methods of the other class were reported.
- `getattr(core, name, None)` passed on as a value, not called, added nothing, and a called one
  only reached methods defined in the receiver's own class, not its mixins.
- `background_tasks.add_task(Cleanup(user).run)` passes a method of an instance built in the
  argument; only names were resolved there.
- A class statement inside a function, as a test that checks a metaclass or `__init_subclass__`,
  and a module-level class registered by `__init_subclass__`, were reported although their
  statements run code.

pytest:

- `pytest_asyncio.fixture` did not register fixtures; a decorator naming a patcher assigned at the
  top of a module (`patch_add = patch.object(Proxy, "add_logs")`) did not remove the mock
  argument; `parametrize("a, b," " c")` joins literals; `from .fixtures import *` of a package
  whose `__init__` star-imports its modules brought nothing; fixture arguments with default
  values were requested; top-level code of `conftest.py` did not run.
- `pytest_plugins` names resolve from the directory above a conftest's outermost package, and a
  plugin's fixtures belong to the session of the conftest naming it: in the monorepo, services
  define fixtures of the same names in their plugins, and the last one hid the others.

## Decision

1. **Imports.** An absolute import whose first part is a top-level project module, or whose
   whole name exists from the root, names that. Otherwise it is looked up beside the importer in
   the directories that are no regular package, innermost first. A candidate there is taken when
   it is a module, holds a module the statement imports from it, starts with a regular package,
   or starts with a name of which the root holds a portion as well; so `alembic/` beside
   `env.py` does not shadow the installed package for `from alembic import context`, and a
   namespace subpackage of a script directory still resolves. A name found nowhere else names
   the one package of that name kept in a directory of its name (`libs/common/common`), if there
   is exactly one; such a match only adds reachability.
2. **Migrations** are the world `production:migrations`: its roots are the migration modules,
   which their tool imports, and their callbacks stay conservative, retained contracts
   (ADR-0013, ADR-0017). An unresolved `RunPython` callback makes only this world partial.
3. **Workers.** `faststream.FastStream` and `faststream.asgi.AsgiFastStream` build applications,
   as do taskiq schedulers (`taskiq scheduler`), also through project subclasses of any listed
   constructor; a top-level class assigning or annotating `functions` or `cron_jobs` in a module
   importing `arq` is an arq worker whose class is the root. Their decorator registrations are
   protected by ADR-0008. A taskiq worker (`taskiq worker module:broker`) is not a root yet.
4. **Dispatch gated by modules.** An unresolved method dispatch protects a method only once the
   module defining it may run in the world, since an instance exists only after its class
   statement ran. The assumption is that instances come from code of the same world: a call of a
   known deserializer (`pickle`, `dill`, `cloudpickle`, `joblib`, `jsonpickle`, `shelve`, unsafe
   `yaml` loaders, `torch.load`, `numpy.load`, `pandas.read_pickle`), which may build instances
   of any class and import its module itself, opens every gate of the world. Serializers that
   frameworks run implicitly, such as a task queue configured to pickle, are outside this and
   need a keep contract. `import_module` of `f"{obj.__module__}.suffix"` protects `M.suffix` only
   once `M` may run, and at once when `M` is a directory without `__init__.py`; a computed name
   protects the modules that match its constant prefix and suffix, with their packages, and a
   relative name is resolved against its `package` argument, or matches every module.
5. **Types.** An annotation gives a type only when it names exactly one project class. A `self`
   field has a type only when every assignment to it in the methods of its class and of the
   class's project subclasses is an instance of one class or `None`; an assignment of unknown
   class, a tuple, loop, or `with` target, `setattr(self, ...)`, and an assignment to an
   attribute of that name on another object leave it without one. An annotation `self.name: T`
   gives the type `T` unless an assignment is known to be of a class that is no subclass of `T`.
6. **Values.** `getattr` with a computed name protects the methods of a receiver of known type,
   of its project bases and subclasses, called or not, and the top-level definitions of a
   project module receiver; an argument `Cls(...).method` escapes as the method it names. An
   instance of a project class passed to an external consumer exposes the class's methods, as
   passing the class does (ADR-0008), since a library may call a protocol method such as an
   SMTP handler's `handle_DATA`; builtins, which use only special methods, and the modeled
   Dishka and FastAPI calls are excepted.
7. **Class statements.** A class whose creation runs a project metaclass, its own or a base's, or
   a project base's `__init_subclass__`, is kept, with the hooks, where its statement runs: in the
   nearest enclosing function, or the module. A class without such hooks that nothing uses is
   still reported, wherever it is defined.
8. **pytest.** Fixtures of `pytest_asyncio.fixture` count; assigned patchers remove their mock
   arguments; string arguments are read as Python evaluates them; star imports are transitive;
   fixture arguments with defaults are not requested; conftest and plugin modules are roots.
   `pytest_plugins` fixtures are visible under the directory of the module that names them,
   and serve a request that no fixture of its session answers; installed `pytest11` plugins
   stay global. A fixture's arguments may also resolve to fixtures of their names defined below
   the fixture's directory, as pytest resolves them from the requesting test.

`MODEL_REVISION` becomes `python-fastapi-dishka/15`, with ADR-0021. The capability revisions are
not bumped: the model revision is part of the method (ADR-0021), and it changes with them.

## Consequences

- The monorepo is complete, with 764 findings in about 70 seconds and a 113 MB report; the
  audited single-service projects report the same findings as before except one confirmed
  `RCH004`, a service class only tests use. Rounds of 160 sampled monorepo findings found 26,
  18, and finally 1 false one, the library-called handler that the instance rule above covers;
  7 of the last round run only through roots the analyzer does not read (below), and 152 were
  confirmed.
- An independent review of this change set found that the first versions of the field rule,
  the import rule, the module gate, the loaded-module rule, and the class-statement scope made
  findings of code that runs, each reproduced in a minimal project; decisions 1, 4, 5, and 7 are
  the corrected rules, and `corpus/python/deserialized_receiver`, which revision 14 passes, guards
  the gate's assumption.
- Corpus cases fail on revision 14: `corpus/frameworks/fastapi_monorepo_service_packages`,
  `message_workers`, `fastapi_background_task_method`, `pytest_class_and_conftest_effects`,
  `pytest_plugins_package_prefix`, `django_runpython_keywords`, and `corpus/python/`
  `branch_assigned_field`, `union_annotated_receiver`, `getattr_method_by_name`,
  `unknown_receiver_needs_module`, `loaded_module_submodule_import`, `class_creation_hooks`,
  `instance_passed_to_library`.
  Unit tests in `tests/test_pytest_semantics.py` and `tests/test_frameworks.py` cover conftest
  packages, plugin sessions, fixture patterns, and the migrations world.
- Roots the analyzer does not read remain limitations: commands in `docker-compose` files or
  Dockerfiles, such as an alternative `uvicorn svc.profiling:app`, a test suite run by explicit
  paths, classes named in logging configuration files, files copied over the standard library,
  and frameworks that deserialize implicitly. `[[tool.deadtrace.worlds]]` and
  `[[tool.deadtrace.keep]]` declare them.
- Worlds per service worker make the monorepo's report larger; ADR-0021 reads reports up to
  256 MiB, and a report schema listing each guard once is the next lever.
