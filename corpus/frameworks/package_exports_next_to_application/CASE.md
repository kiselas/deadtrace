# A library with a command line

`pkg` is a library that also ships a command line: `pkg/cli.py` builds a Typer application. Its
`__init__.py` re-exports `helper` with `from pkg.core import helper as helper`, which is the
declaration that `helper` is part of the API users import, and lists `Client` in `__all__`.
A Typer application is a root, so the library has no world of its own, and nothing in the project
calls `helper` or `Client`. Reporting them is unsafe. `dead` is exported by nothing and called by
nothing and stays a candidate.
