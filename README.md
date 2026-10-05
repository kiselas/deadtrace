# Deadtrace

Deadtrace is an open-source, explainable dead-code analyzer for Python applications. It models
framework registrations, dependency injection, callbacks, lifecycle hooks, and test consumers
instead of treating “no textual references” as proof that code can be deleted.

> **Alpha candidate:** scans are static and read-only. Findings are review units, never claims that
> deletion is safe. PyPI publication is intentionally deferred.

## What works now

- world-local reachability with separate resolved and conservative execution;
- Python references, closures, inheritance and `super()`, method overrides, decorators, and
  evaluated annotations, with conservative protection for values of unknown type and for
  functions registered by decorators of frameworks that are not modeled;
- special methods, hooks that external base classes may call on their subclasses, modules
  and symbols named by strings, and modules imported with `importlib.import_module`;
- module execution by imports anywhere in running code, package initializers, star
  imports, package re-exports, and names bound differently in `try` or `if` branches;
- `@overload` signatures with their implementation, single-underscore library hooks such as
  IPython's `_repr_html_`, and the methods of classes handed to code outside the project;
- deterministic component findings with stable fingerprints;
- FastAPI applications, routers, nested `Depends`, lifespan, selected hooks, background tasks,
  Pydantic hooks, and a bounded `create_app` pattern;
- Dishka `@provide`, class providers, aliases, `from_context`, `FastapiProvider`, `@inject`,
  `DishkaRoute`, multiple applications/containers, and generator cleanup chains;
- a separate pytest world that resolves fixtures, parametrization, `patch` arguments,
  `pytest_plugins`, imported fixtures, hooks, inherited test methods, and the configured
  `python_files`, `python_classes`, and `python_functions` the way pytest does;
- conservative property/protocol/metaclass hooks and historical Django `RunPython` retention;
- Django settings as application roots: installed applications' `models`, `admin`, template
  tags, management commands, and `AppConfig`, the ASGI and WSGI modules, relocated
  migrations, and the modules settings name by string; nested `Meta` and Pydantic `Config`
  classes; Alembic environments and revisions;
- PEP 621 console, GUI, and plugin entry points as statically read, provenanced production roots,
  including values such as a Typer application, and the hooks and fixtures of `pytest11`
  plugins; Typer and Click commands;
- automatic worlds when none are configured: scripts with a main guard and `__main__`
  modules, applications of Flask, Celery, Starlette, Litestar, aiohttp, Sanic, Quart,
  Falcon, Bottle, Typer, and FastStream, taskiq schedulers, arq workers, database migrations,
  uncalled FastAPI factories, Celery task autodiscovery, programs that Compose files,
  Dockerfiles, `Procfile`s, Makefiles, and shell scripts start, classes that configuration
  files name, and otherwise a library's public API;
- explicit external keep contracts, saved explanations, baselines, report comparison, and CI exit
  policies;
- schema-1 JSON, text output, compatibility guards, and a performance benchmark artifact.

Unknown assembly, conditional activation, Dishka components/decorators, unresolved plugins, and
untested pinned framework versions weaken the affected world instead of generating stronger
negative findings.

Source discovery skips virtual environments, `site-packages`, `node_modules`, and hidden
directories, and names what it skipped. When a scan reports little because unknown
boundaries protect most code, the report names the widest ones and where they are.

## Install from this repository

Deadtrace requires Python 3.12. With [uv](https://docs.astral.sh/uv/):

```console
uv sync --locked --all-groups
uv run deadtrace --help
```

To test the distributable package without importing the source tree:

```console
uv build
uv run --isolated --no-project --python 3.12 \
  --with ./dist/deadtrace-0.1.0a0-py3-none-any.whl deadtrace --version
```

The interpreter is selected explicitly because `--no-project` ignores `.python-version`, and the
default `python` on PATH may be older than 3.12.

Exercise scanning and saved artifacts from the installed wheel with:

```console
uv run --isolated --no-project --python 3.12 \
  --with ./dist/deadtrace-0.1.0a0-py3-none-any.whl python scripts/wheel_smoke.py
```

The smoke script uses a temporary directory, rejects a source-tree package import, and checks
inventory, analysis, determinism, explanations, baselines, comparisons, and no target execution.

## Quickstart: FastAPI + Dishka

The reference application contains a live endpoint → service → repository path and one registered
but unrequested legacy binding:

```console
uv run deadtrace scan corpus/reference/fastapi_dishka_basic
uv run deadtrace scan corpus/reference/fastapi_dishka_basic \
  --format json --output deadtrace-report.json --require-complete
uv run deadtrace explain RCH003-FINGERPRINT --report deadtrace-report.json
```

Use the exact fingerprint printed by the scan. `explain` reads only the saved report, so changing
the project cannot silently change the explanation.

### Configuration

```toml
[tool.deadtrace]
require-complete = true
exclude = ["testdata/**"] # data the project never runs; excluded code protects nothing
report-exclude = ["generated/**"] # affects presentation, never the source universe
max-steps = 100000 # optional; by default the budget is sized from the graph

[[tool.deadtrace.worlds]]
profile = "production"
scenario = "web"
roots = ["app.main:app"]
frameworks = ["python", "fastapi", "dishka", "pydantic"]

[[tool.deadtrace.keep]]
target = "app.plugins:external_hook"
reason = "Loaded by the deployment platform"
profiles = ["production"]
```

A world's `frameworks` list is declarative (ADR-0014): it records the frameworks the world is
expected to use, while every capability applies to every world, since switching one off could
only remove protection. Unknown names are rejected.

External keeps propagate conservatively through the callback body. They do not become fabricated
resolved calls and are not equivalent to hiding a warning.

## Findings and exit codes

| Code | Meaning |
| --- | --- |
| `RCH001` | Unreached semantic component in complete production worlds |
| `RCH002` | Route on a router not published by a modeled application |
| `RCH003` | Registered Dishka binding with no established demand |
| `RCH004` | Production code reached only from a complete pytest world |

Exit code `0` means the command completed; limitations may still be present. `1` is emitted only by
an explicitly selected finding policy (`--fail-on-findings`, `--fail-on-new`). `2` means an
operational error or a failed completeness/comparability requirement, and takes priority over `1`.

## Baseline and report comparison

A baseline records reviewed debt without removing findings from the report or changing the graph:

```console
uv run deadtrace baseline create deadtrace-report.json \
  --output deadtrace-baseline.json --reason "reviewed before adoption"
uv run deadtrace scan . --format json --baseline deadtrace-baseline.json --fail-on-new
```

Refreshing a baseline keeps only exact reviewed entries and does **not** accept new findings unless
that decision is explicit:

```console
uv run deadtrace baseline update deadtrace-baseline.json deadtrace-report-new.json \
  --output deadtrace-baseline-refreshed.json
uv run deadtrace baseline update deadtrace-baseline.json deadtrace-report-new.json \
  --output deadtrace-baseline-reviewed.json --accept-new --reason "reviewed new debt"
```

Compare two reports directly; Git access is not required:

```console
uv run deadtrace compare before.json after.json --fail-on-new --require-comparable
```

Changing the model revision, configuration, capabilities, or the support of target dependency
versions produces `partially_comparable`, not a misleading “all findings resolved” result.
Reports without a common execution world are `incomparable`; incomplete inputs can never be
`comparable`. Added tests, routes, scripts, and applications are source changes: added and
removed source files, worlds, and roots are listed separately from finding changes, and a
baseline stays comparable across them. Fingerprints depend on a finding's code and members only.
When a new model revision makes a baseline incomparable, `baseline update` carries reviewed
entries over by code and members.

Create an inspectable troubleshooting artifact without source text, file paths, symbol names,
configuration values, environment variables, or object values:

```console
uv run deadtrace support-bundle .
uv run deadtrace support-bundle . --output deadtrace-support.json
```

When `--output` is used, Deadtrace prints a privacy/content preview before writing the bundle.

## Supported and guarded behavior

The oracle environment currently pins FastAPI 0.141.1, Dishka 1.10.1, and HTTPX 0.28.1. The
modeled subset is supported for FastAPI `>=0.100,<1` and Dishka `>=1.0,<2` (ADR-0018): an exact,
different version found in `uv.lock` or `pyproject.toml` inside the range is reported as `DT4002`,
and one outside it creates `DT4001` and blocks strong negative findings. An unpinned dependency is
not presented as version-verified.

A pattern for which a complete world reports code that may run as unreached is a contract
violation. It is recorded under [fixtures/known-violations](fixtures/known-violations/README.md)
before it is fixed. Recorded cases, including receiver-flow violations across branches and loop
iterations fixed in model revision 23, now live in `corpus/`. A method whose name is also used on a value of unknown type is protected
rather than reported, and a function under an unmodeled framework's decorator is protected in
any world that loads its module. The methods of a class with an external base, other than
builtins, `abc`, `typing`, `pydantic.BaseModel`, and `dishka.Provider`, are protected once the
class is used, and so are the methods of a class handed to code outside the project.

Dishka conditional activation and components/decorators are detected but guarded. Dynamic imports,
unrestricted reflection, implicit descriptors/metaclasses, arbitrary pytest plugins, and general
Python dispatch are not claimed as fully modeled; known project hooks are protected transitively.
Static Django `RunPython` callbacks are a safety-only retention capability, not Django application
support. Dynamic package entry points are not executed; they emit `DT4102`, while explicit worlds
remain a deterministic override. Run `deadtrace doctor PATH` to see the capability and limitation
state for each world.

## Corpus and development

```console
uv run deadtrace cases validate fixtures/cases
uv run deadtrace cases validate corpus
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest --cov
uv run deadtrace benchmark corpus/reference/fastapi_dishka_basic --runs 5
uv build
```

`corpus/` contains executable semantic projects with independent expectations for worlds, findings,
limitations, and target states. Oracle tests execute only the trusted included reference project;
ordinary `scan` never imports or executes target modules and does not use the network.

## Project documentation

The canonical implementation plan is [ROADMAP.md](ROADMAP.md). Architecture decision records are
in [docs/adr](docs/adr/README.md). The analysis contract, architecture notes, support matrix, and
acceptance matrix are planned for `docs/` and have not been written yet. Repository policies are
in [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md),
[GOVERNANCE.md](GOVERNANCE.md), and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

The [2026-10-01 repository audit and improvement plan](docs/audit-2026-10-01.md) records current
verification and remaining priorities. [Methodology](docs/methodology.md) is a reviewed research
proposal; it does not change the active milestone or authorize future target execution.

## License

Apache License 2.0. See [LICENSE](LICENSE).
