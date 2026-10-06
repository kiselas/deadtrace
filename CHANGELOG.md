# Changelog

All notable changes will be documented here. The project follows Semantic Versioning once public
compatibility commitments are defined; alpha schemas may change between releases.

## 0.1.0a2 - 2026-10-06

### Measured

- On two blind cohorts of public GitHub projects (77 and 76 repositories, 195 and 194 reviewed
  findings), 49.7% and 39.2% of the findings were true. Findings remain review units. The
  per-finding verdicts and the false-finding classes are in `docs/field/2026-10-cohort.md`.

### Added

- Python 3.13 and 3.14 are supported runtimes; CI runs the tests and the installed-wheel smoke on
  3.12, 3.13, and 3.14. Reports of the 123 corpus projects are byte-identical between 3.12 and 3.13.
- `--debug` (or `DEADTRACE_DEBUG=1`) shows the traceback of an internal error. Without it an
  unexpected exception ends as one line, `DT0001`, with exit code 2, instead of a traceback.
- Tests that feed hostile inputs (deeply nested expressions, NUL bytes, invalid encodings, broken
  configuration and lock files, huge lines, cyclic star imports) to `scan`, `doctor`, and
  `support-bundle`.

### Fixed

- Model revision `python-fastapi-dishka/35` (ADR-0053): a `test*.py` module that defines a
  `unittest.TestCase` is collected, as `python -m unittest discover` does by default.
- Model revision `python-fastapi-dishka/34` (ADR-0052): a project whose `pyproject.toml` declares a
  distribution without a console script roots that package's public API as a library next to its
  scripts and examples (a distribution with its own command keeps its worlds); four libraries of the public cohort had no production root for their API.
- Model revision `python-fastapi-dishka/33` (ADR-0051): an application built in a test module is a
  fixture, not a production world, and no longer hides a library's public API (a Flask fixture in
  `conftest.py` made every public class of a library "test-only").
- Model revision `python-fastapi-dishka/32` (ADR-0050): classes derived from Django and Django REST
  framework test cases are collected as unittest cases; on a public held-out cohort they were the
  largest class of false findings.
- Analysis runs with a Python recursion limit of 10,000: a 3,000-link attribute chain exhausted the
  default 1,000 on Python 3.14. JSON artifacts nested deeper than 200 levels are rejected the same way
  on every interpreter (3.14's parser accepted 10,000 levels).
- A source file whose expression nesting exceeds the parser's recursion limit raised an unhandled
  `RecursionError` and aborted the scan; it is now a `DT1001` for that file only.
- A Python source file larger than 16 MiB is skipped with `DT1001` instead of being read whole; one
  18 MB generated file used to take two minutes.
- The `DT1001` syntax-error message says that syntax newer than the interpreter running Deadtrace is
  reported the same way.

## 0.1.0a1 - 2026-10-05

## 0.1.0a1 - 2026-10-05

First public alpha for Python 3.12. Scanner model `python-fastapi-dishka/31`; inventory schema 0,
semantic report schema 1. Findings require human review; no deletion-safety guarantee is made.

- Static scanning, saved explanations, baselines, report comparison and diagnostic bundles.
- Documented analysis contract, supported scope and exact-commit release acceptance.
- Python receiver control-flow joins, finite local dispatch names, external nominal reflection,
  stored literal callable/re-export protection, and public object-field/declared-return API closure
  accumulated through ADR-0033 to ADR-0046.
- A single CI-built wheel and source distribution are sealed with SHA-256 checksums, exercised
  on Linux and Windows, and published through GitHub OIDC without rebuilding (ADR-0049).
- The independently pinned `object.__setattr__` recall gap remains guarded on model 31;
  the selected model-32 refinement is deferred. General dynamic dispatch and unmodeled behavior
  retain conservative protection. Field measurements are not market-wide precision claims.

The entries below describe the development history included in this first public distribution.

### Added

- A portable installed-wheel smoke check exercises inventory, analysis, determinism, explanations,
  baselines, comparisons, and no target execution on both CI operating systems (ADR-0030).
- Hypothesis `@given` arguments, plugins loaded with `-p` in `addopts`, `unittest.main()`, aliases of
  `unittest.TestCase`, conditional bases and imports, scripts run by file name, and lazy export
  tables are understood (ADR-0028).
- Dead methods are found in more classes: a class a Dishka binding builds, an instance kept in a
  list or a dictionary, and a class read for an attribute no longer keep all their methods; an
  implementation of an abstract method is retained with its class (ADR-0027).
- `[tool.deadtrace].exclude` leaves data directories out of the source universe; reports list
  the excluded files (ADR-0018).
- `cli.commands` capability: Typer commands and callbacks, and Click subcommands and groups.
- `DT4002` reports a pinned FastAPI or Dishka version that is supported but not oracle-tested.
- Text reports and `doctor` name the widest guards of production worlds, with the number of
  definitions only they keep possibly running and where they are, when unknown boundaries
  protect much of the project.
- Reports list the skipped environment and tool directories
  (`source_universe.skipped_directories`, ADR-0015).
- `alembic.migrations` capability: Alembic environments and revision functions are external
  contracts (ADR-0017).
- A manually dispatched `Performance` workflow that benchmarks the generated 50k-line scale and
  service fixtures from the built wheel on Linux and Windows, uploads the artifacts, and fails
  above the 30-second or 1-GiB budget (`benchmarks/check_budget.py`).
- Installable Python package and `deadtrace` CLI.
- Read-only inventory of functions and classes.
- World-local reachability, conservative unknown propagation, retention, and negative gates.
- FastAPI, Dishka, Pydantic, and pytest semantic capabilities with guarded unsupported patterns.
- Stable review groups `RCH001`–`RCH004`, saved explanations, and schema-1 semantic reports.
- Explicit baselines, report comparison, CI finding policies, doctor, and benchmark commands.
- Safe baseline updates and three-state report comparability with explicit source/input changes.
- Privacy-conscious troubleshooting bundles with a pre-write content preview.
- Static PEP 621 entry-point worlds with root provenance and guarded dynamic metadata.
- Automatic worlds without configuration (ADR-0011): `production:scripts` for main guards
  and `__main__` modules, one world per application of Flask, Celery, Starlette, Litestar,
  aiohttp, Sanic, Quart, Falcon, Bottle, or Typer, and `production:library` for the public
  API of projects without applications or entry points, each with its root provenance.
- Executable semantic corpus and pinned FastAPI/Dishka oracle application.
- Safety retention for static Django `RunPython` migrations and implicit Python
  property/protocol/metaclass hooks.
- Whole-source snapshot retry with `DT1002` fallback when files keep changing during a scan.
- Experimental inventory schema 0 remains available through `--inventory-only`.
- Strict `[tool.deadtrace]` configuration and report exclusions that do not alter analysis scope.
- Six independently described seed cases and a lexical manifest validator.
- Windows/Linux CI, wheel smoke testing, contribution, governance, and security policies.
- Architecture decision records under `docs/adr/`, starting with the decision to keep them in
  the repository and the acceptance of Rich 15.
- Sub-stage timings and deterministic size counters for every analysis run
  (`deadtrace.timing`), threaded through source collection, inventory, the Python frontend,
  and framework modeling without changing what any stage computes.
- `benchmarks/profile_scan.py` and the first committed 50k-line profile under
  `benchmarks/results/`.
- `benchmarks/generate_service_fixture.py`, a deterministic FastAPI/Dishka/Pydantic service whose
  size grows with symbols, calls, routes, and bindings, and `benchmarks/stage_installed_sources.py`,
  which copies the sources of locked third-party packages as scan targets without importing them.
  The scale fixture alone produces no edges or framework objects and could not show those costs.
- `fixtures/known-violations/`: cases where a complete world reports code that may run as
  unreached, pinned by `tests/test_known_violations.py` (ADR-0006), and the safety-only case
  expectation `not_candidate`. Twenty-eight were recorded and are now met.

### Changed

- Model revision `python-fastapi-dishka/19` (ADR-0026), from 57 more installed packages: the API a
  library's `__init__` re-exports explicitly is a root next to its command line (world
  `production:exports`); quoted annotations name their classes; `return locals()` hands nested
  functions on; `self.name` in a mixin reaches the member of a subclass; a member missing on a typed
  receiver reaches subclass members and test stand-ins.
- Model revision `python-fastapi-dishka/18` (ADR-0025), from 39 installed libraries: overrides of
  public methods in private implementation classes, module `__getattr__` and `__dir__`, classes
  named by a subscripted annotation, methods passed as values with their overrides and branch
  definitions, `globals()[name]` lookups, test modules that create their tests when imported,
  main-guard programs in test directories, classes derived from a computed base, a definition
  and an import that bind one name, and `request.getfixturevalue("name")` in plugins.
- Model revision `python-fastapi-dishka/17` (ADR-0024): test functions and classes that a test
  module imports by name or with `*` are collected in the importer and resolve their fixtures from
  its directory and conftests; a directory without Python files says so.
- Model revision `python-fastapi-dishka/16` (ADR-0023): commands in Compose files, Dockerfiles,
  `Procfile`, Makefiles, shell scripts, supervisord programs, and systemd units that start
  `uvicorn`, `gunicorn`, `hypercorn`, `daphne`, `granian`, `faststream`, `taskiq`, `arq`,
  `dramatiq`, `celery -A`, `python -m`, `python script.py`, or `locust -f` root the world
  `production:commands` when no worlds are configured; gunicorn configuration hooks, locust
  users, and classes that logging configurations name by `class` or `()` are conservative
  roots with their methods (`deployment.commands` capability). A configured world named
  `production:migrations` is rejected, and deployment reading has the timing stage
  `frontend.deployment`.
- Model revision `python-fastapi-dishka/15` (ADR-0021): reports and baselines stay comparable
  when tests, routes, scripts, or applications are added, when dependencies other than
  unsupported FastAPI or Dishka versions change, and when only the analyzer version changes;
  `compare` lists added and removed worlds and roots as source changes. Fingerprints no longer
  include worlds, so every fingerprint changes once. `baseline update` carries reviewed entries
  over by code and members, and an incomparable baseline names the method fields that differ.
- The same revision (ADR-0022), from a 624k-line monorepo: imports inside services that hold a
  package of their own name, namespace service packages, and editable libraries such as
  `libs/common/common` resolve; migrations run in their own world `production:migrations`;
  FastStream applications, taskiq schedulers, and arq workers root worlds; unresolved method
  dispatch and `import_module(f"{obj.__module__}.x")` protect only code whose module may run;
  a union annotation gives no single type; `self` fields take the annotated type or the one
  class all methods assign; `getattr` values of known receivers and `Cls(...).method`
  arguments and project instances passed to libraries escape; deserializers such as
  `pickle.loads` open the module gates; classes created for a metaclass or `__init_subclass__`
  are kept; `pytest_asyncio.fixture`, assigned patchers, joined string
  literals, transitive star imports, fixture defaults, conftest top-level code, `pytest_plugins`
  per session, and `RunPython(code=...)` are modeled.
- Reports and baselines are read back up to 256 MiB, and `scan` warns when a report is larger;
  project inputs keep the 16 MiB limit.
- A finding's explanation lists its worlds' limitations other than guards once, with counts, and
  the number of guards, instead of copying every guard; reports of single-service projects are
  up to ten times smaller and stay below 16 MiB.
- Model revision `python-fastapi-dishka/14` (ADR-0020): `Sub.member` with an inherited member
  uses `Sub`, so the hooks bases call on it are reached; pytest-click fixtures are known.
- Model revision `python-fastapi-dishka/13` (ADR-0019): a FastAPI factory that returns its
  application inside a wrapper, and the uncalled function that calls it, root a web world; a
  package imports its own submodules by absolute name; a `pytest11` plugin's package is also a
  library, and the classes its fixtures return expose their public methods; setuptools `build`
  copies are skipped; nested test classes are collected.
- Model revision `python-fastapi-dishka/12` (ADR-0018): FastAPI `>=0.100,<1` and Dishka
  `>=1.0,<2` are supported, and only versions outside those ranges weaken worlds (`DT4001`);
  methods of test stand-ins for values from outside the project, fixtures requested with
  `getfixturevalue` or lazy fixtures, and fixtures of `pytest11` plugins are reachable;
  importing a module that is loaded already and `with` targets of outside managers add no
  unknown dispatch; a project without roots reports `DT3004`.
- The solver marks each distinct boundary target set once per world, and the pytest model no
  longer records per-test fixture visibility; results are unchanged.
- Model revision `python-fastapi-dishka/11` (ADR-0017), from an audit of six real projects:
  `include_router` in helpers and loops over literal router lists; entry points naming a
  top-level value such as a Typer application; calls inside annotations; attribute chains
  through enumeration members; nested `Config` and `Meta` classes; Django `AppConfig`,
  ASGI/WSGI modules, and `MIGRATION_MODULES`; modules loaded from paths or by computed names and
  their attributes; `Protocol` receivers and test stand-ins; pytest marks and fixtures as
  transparent decorators; closures of retained declarations.
- pytest facts are local to the tests world, and the model resolves arguments, parametrization,
  plugins, fixture imports, collection patterns, inherited test methods, hooks, and xunit setup
  the way pytest does (ADR-0016).
- Source discovery skips virtual and conda environments, `site-packages`, `node_modules`,
  `__pypackages__`, and hidden directories; a `src` directory is a package when code imports it,
  and absolute imports also resolve against a script's own directory (ADR-0015).
- Limitations that every world shares, such as an unreadable file, are printed once in text
  reports.
- Text reports and `doctor` count identical limitations once and summarize worlds with many
  kinds of `DT2002` guard in one line; the JSON report still lists every guard.
- A world's `frameworks` list accepts every modeled framework and is documented as declarative
  (ADR-0014): every capability applies to every world.
- Model revision `python-fastapi-dishka/10` (ADR-0013): a module assigning `INSTALLED_APPS`
  is a Django settings module that imports its applications' packages and `apps`, `models`,
  `admin`, template-tag, and management-command modules, registers model classes, and
  instantiates commands; without configuration each settings module roots a
  `production:django` world. A string may name a module through an attribute it binds.
- Model revision `python-fastapi-dishka/9` (ADR-0012): `@overload` signatures belong to
  their implementation; single-underscore hooks such as `_repr_html_` are protected like
  special methods; a nested function bound in one branch is reachable through its name; a
  class that escapes exposes its methods, except to `isinstance`, `issubclass`, and
  consumers a capability models.
- Model revision `python-fastapi-dishka/8` (ADR-0011): FastAPI factories that no module
  calls are applications, and a factory's constructor resolves in its own module; Celery
  `autodiscover_tasks()` may import every `tasks` module. Without `max-steps`, the solver
  budget is twice the node count instead of 100,000 steps.
- Model revision `python-fastapi-dishka/7` (ADR-0010): an import statement runs the project
  modules on its path wherever it executes, whatever it binds, except under
  `if TYPE_CHECKING:`; a module runs after its package; imports in nested blocks and in
  functions bind names; star imports and package re-exports resolve, for configured roots
  and entry points too; a name bound in alternative branches reaches every alternative.
- Model revision `python-fastapi-dishka/6` (ADR-0009): every special method of a used class,
  and the methods of classes with an external base that may call them, are protected
  conservatively, with builtins, `abc`, `typing`, `pydantic.BaseModel`, and `dishka.Provider`
  exempt; strings that name a project module or symbol are references; `importlib`
  imports by literal, f-string prefix, or unknown name reach those modules. `DT2002` appears
  only for boundaries that protect a node not otherwise resolved.
- Model revision `python-fastapi-dishka/5` (ADR-0008): references to project functions and
  classes, member-to-owner and inheritance edges, method resolution order and `super()`, class
  hierarchy dispatch, conservative dispatch on values of unknown type, decorator application and
  registration, evaluated annotations, Python name scoping with local shadowing, and Pydantic
  hooks whenever their model is used. The thirteen recorded known violations are met and moved
  to `corpus/`; `EdgeKind` gains `member`, `inherit`, and `annotation`. `Service` in two Dishka
  corpus cases is now live through its endpoint annotation.
- The analysis parses with the standard-library `ast` module instead of LibCST, which is no
  longer a dependency (ADR-0007). The 50k-line fixtures scan in 0.6 and 1.2 instead of 11.8 and
  16.3 seconds and mypy's 129k lines in 2.6 instead of 65.8, with peak RSS roughly halved.
  Reports are byte-identical; `DT1001` messages for unparseable
  files now read `syntax error at line L, column C: <message>`. The benchmark artifact is schema 4:
  `descriptor.libcst_version` is replaced by `descriptor.parser`.
- Symbol, member, container-binding, and adjacency lookups use indexes built once per analysis
  instead of scanning whole collections per query, and the frontend walks each called function's
  body once instead of once per call site (ADR-0005). On the 50k-line service fixture the affected
  stages take 2.2 instead of 15.9 seconds at the median, and they no longer grow faster than the
  source. Reports are byte-identical.
- Each module is parsed once and its source positions are resolved once; inventory, the
  Python frontend, and framework discovery share the result (ADR-0004). The 50k-line
  benchmark is 2.7 times faster at the median with byte-identical reports.
- The benchmark artifact is schema 3: `collect.inventory_parse` is replaced by
  `collect.parse`, which covers the single parse and position pass.
- The benchmark artifact is schema 2: it records host and tool versions, deterministic
  counters, per-sub-stage seconds, a separate `report_seconds`, and the list of volatile
  fields. `memory_note` moved to `notes.memory`.

### Fixed

- Source traversal errors and non-text encoding cookies produce `DT1001` instead of silently
  dropping source or crashing. Configuration reads enforce the 16-MiB input limit; invalid UTF-8
  uses existing input diagnostics. Invalid modeled dependency versions produce the `DT4001`
  compatibility guard (ADR-0030).
- Package API worlds follow re-exports from all conditional imports, including alternatives to
  absent compiled modules. Class-body and chained annotations retain the classes they name
  (ADR-0029, model revision 22).
- A report with input issues is comparable with a baseline created from it; the issues were
  stored as tuples and read back as lists.
- The `pytest.fixtures` capability is listed whether or not the project has tests, so a first
  test no longer changes the analysis method.
- Repository-wide LF normalization through `.gitattributes`, so a Windows checkout made with
  `core.autocrlf=true` no longer fails `ruff format --check` on unmodified files.
- The documented wheel smoke command selects Python 3.12 explicitly instead of relying on the
  default interpreter on PATH.
- Strict mypy no longer fails on Linux. The Windows-only peak working set helper now declares
  its platform precondition instead of relying on a runtime `AttributeError`, which `ctypes`
  raises only at runtime and which mypy reports as `Module has no attribute "WinDLL"`.

### Safety

- Static scans never import or execute target modules.
- Unsupported target versions and unresolved framework assembly block strong negative findings.
- Baselines annotate findings but never suppress blockers or alter semantic analysis.
