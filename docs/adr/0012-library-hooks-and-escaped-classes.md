# ADR-0012: Overloads, library hooks, branch-bound functions, and escaped classes (model revision 9)

**Status:** Accepted, 2026-09-24.

## Context

The library worlds of ADR-0011 gave the first findings on real packages. Of rich's 16 members and
pygments's 4, five were dead code; the others came from four patterns, recorded as known violations
(ADR-0006):

- `@overload` signatures were reported apart from the implementation that follows them, although
  `typing` keeps them for `typing.get_overloads` and type checkers read them;
- IPython and Jupyter call `_repr_html_`, `_repr_mimebundle_`, and similar single-underscore hooks
  on the objects they display, and only double-underscore names were protected;
- a nested `def write` in one branch and `write = print` in another made `write` a plain local
  name, so the call never reached the nested function;
- code outside the project that receives a class may call its methods, as `ctypes` calls
  `from_param` on a class in `argtypes`, and nothing protected them.

## Decision

1. **Overloads.** A definition decorated with `typing.overload` or `typing_extensions.overload`
   belongs to the next definition of its name without that decorator: the implementation has an
   `annotation` edge to each of its signatures, so they live and die together.
2. **Single-underscore hooks.** A method named `_name_`, with one underscore on each side, is
   protected like a special method once its class is used. The convention is reserved for protocol
   hooks: `enum` uses `_missing_`, IPython `_repr_html_` and `_ipython_display_`.
3. **Branch-bound nested functions.** When a function binds a name both by a nested definition and
   otherwise, a use of the name may reach the nested definition.
4. **Escaped classes.** A project class used as a value that escapes, stored or passed where the
   analysis cannot follow it, exposes its methods and those of its project bases, conservatively.
   A class passed to an unresolved consumer gets an `escaped_class` boundary of its own, which a
   capability that models the consumer, such as `fastapi.Depends` or a Dishka provider, recognizes
   by the class and removes. `isinstance` and `issubclass` only inspect the class and expose
   nothing.

`MODEL_REVISION` becomes `python-fastapi-dishka/9`; `python.direct-flow` moves to revision 5.

## Consequences

- The four cases meet their expectations and move to `corpus/`, which now holds 50.
  `tests/test_python_soundness.py` checks that classes given to `isinstance` or used only in dead
  code expose nothing, that other underscore names stay unreached, that an overload without a later
  implementation is not linked, and that a nested function is reached only where its name is used;
  `tests/test_frameworks.py` checks that a class in `Depends` keeps its unused methods reported.
- rich reports 3 members and pygments 2, all dead code; the probes and the 50k service fixture are
  unchanged.
- Alternating runs on a loaded host, fastest of three per side, `main` first and this change
  second (artifacts in `benchmarks/results/2026-09-24-library-hooks/`): the scale fixture 0.73
  and 0.78 seconds, the 50k service fixture 1.54 and 1.61, mypy 4.13 and 4.11, pygments 2.03
  and 2.23, rich 0.89 and 0.95; peak RSS changes by at most 1 MiB, except rich, 12 MiB lower.
- The methods of a class passed to unmodeled code, such as a registry of handler classes, are
  protected rather than reported. A capability for the registry can narrow this by naming the
  methods it calls.
