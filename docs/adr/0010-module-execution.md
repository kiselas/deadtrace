# ADR-0010: Module execution and import bindings (model revision 7)

**Status:** Accepted, 2026-09-24.

## Context

Only top-level imports that bound a module, function, or class were execution edges, and only
top-level simple statements bound names. Building automatic worlds for Flask found complete worlds
reporting code that runs because a module is imported:

- `from shop.views import bp` imports a value, so `shop.views` never ran and its routes were
  reported;
- `import jobs.nightly` ran `jobs` but not `jobs.nightly`, and the package of a root module never
  ran;
- `from helpers import *`, imports inside functions, and imports in `try` or `if` blocks bound
  nothing, so calls through them resolved to nothing;
- a name bound in alternative branches, such as `try: from fast import speedup` with an
  `except ImportError:` fallback, or a function defined on both sides of a platform check,
  reached only the last binding;
- `from pkg import helper`, where `pkg/__init__.py` re-exports `helper` from `pkg._impl`, did not
  resolve, so the most common way to publish a package API reported the function it publishes.

## Decision

1. **Imports run modules wherever they execute.** An import statement is an execution fact of the
   scope that runs it: a module's top level, a class body, or a function body. It runs each
   project module on the imported path, packages first: `import a.b.c` runs `a`, `a.b`, and
   `a.b.c`; `from a.b import c` runs `a`, `a.b`, and `a.b.c` if that is a module, whatever `c` is.
   Imports under `if TYPE_CHECKING:` bind names for annotations but run nothing.
2. **Packages run before their modules.** Every module has an edge to its nearest project package.
3. **Bindings follow scopes.** Imports in nested blocks of the top level bind module names; the
   last binding wins. Imports in a function bind names in it and in the functions nested in it,
   unless they bind the name locally themselves. A local import of an external package makes the
   name an external value.
4. **Star imports.** `from module import *` binds the names of a project module. A name that no
   definition or import binds resolves through the star imports, most recent first. `__all__` is
   not consulted, which may bind more names than Python does and never fewer.
5. **Re-exports.** A full name that is not a definition is followed through the imports of the
   longest module prefix it starts with, repeatedly: `pkg.helper` names `pkg._impl.helper`.
   Configured roots, keep targets, and entry points resolve the same way. An import cycle
   resolves to nothing.
6. **Alternative bindings.** When several statements bind a top-level name and one of them sits in
   a nested block, whether imports or definitions, a call or reference through the name reaches
   every alternative. Unconditional rebinding keeps the last binding, as before.

`MODEL_REVISION` becomes `python-fastapi-dishka/7`; `python.direct-flow` moves to revision 4.

## Consequences

- Six cases were recorded first (ADR-0006), met their expectations with every protected target
  resolved and no limitation, and moved to `corpus/`, which now holds 41.
  `tests/test_python_soundness.py` adds checks that `TYPE_CHECKING` imports and imports in dead
  functions run nothing, that unconditional rebinding stays precise, that a local name shadows an
  enclosing function's import, and that star imports and re-export cycles bind only what is used.
- Alternating runs on a loaded host, fastest of three per side, `main` first and this change
  second (artifacts in `benchmarks/results/2026-09-24-module-execution/`): the scale fixture
  0.72 and 0.77 seconds, the 50k service fixture 1.60 and 1.81, mypy 6.35 and 5.95, pygments
  1.90 and 1.81, rich 0.64 and 0.67; peak RSS changes by at most 2 MiB. On the probes only the
  re-export probe changes: its false finding is gone.
- A module imported anywhere in code that may run is treated as run, including imports that a
  program guards at runtime; this is sound and costs precision only where a module's top level
  does work.
