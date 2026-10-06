# ADR-0052: A declared distribution roots its package as a library

**Status:** Accepted, 2026-10-06; model revision 34.

The automatic library world existed only for a project without applications, entry points, or
scripts (ADR-0011). On the public cohort (`docs/field/2026-10-cohort.md`) about 70 reviewed
members of four libraries were reported as unreached because the repositories also hold examples,
a console script, or a `pyinstaller` hook: the public API of `tcod`, `redgifs`, `rollbar`, and
`flask_socketio` had no production root while their examples did.

A `pyproject.toml` with `[project].name` declares a distribution. The packages it ships are a
library whose public API its users call, so those packages get the library world next to any
other worlds, with the same public-API rules as ADR-0011 and ADR-0026. The packages are the
normalized distribution name (``Flask-SocketIO`` gives ``flask_socketio``) and the literal
`[tool.setuptools.packages]` and `[tool.hatch.build.targets.wheel].packages` lists, kept only when a
top-level package of that name exists in the source. `packages.find`, dynamic names, and
`setup.py`-only projects are not read; a project that ships a package under another name
configures a world. Root provenance records `declared_distribution`.

This is the policy answer to "is an exported but uncalled name of a library dead": for a declared
distribution it is API, not a finding; for an application it still is. The case
`corpus/frameworks/declared_distribution_library` fails on revision 33.

MODEL_REVISION becomes `python-fastapi-dishka/34`.
