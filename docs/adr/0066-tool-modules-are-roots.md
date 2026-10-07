# ADR-0066: Modules that development tools run are roots

**Status:** Accepted, 2026-10-07; model revision 48.

nox runs `noxfile.py` and calls its `@nox.session` functions; setuptools runs `setup.py`; Sphinx
runs `docs/conf.py` and calls `setup(app)`; fabric, doit and paver run `fabfile.py`, `dodo.py` and
`pavement.py`; mkdocs imports the files `hooks:` lists and calls their `on_*` functions, and
mkdocs-simple-hooks names `module:function`. None of these is imported by project code, so their
functions and the helpers they call were reported as unreached (about 25 reviewed findings in
three cohorts).

The deployment reader (ADR-0023) now records such a file as a `script` reference with `exposed`
set, as it does for a gunicorn configuration: the module is a root of the commands world and its
top-level definitions are conservatively reachable. `conf.py` counts only inside a `docs`, `doc`
or `documentation` directory. `mkdocs.yml` is read as a command file: a `*.py` path in it is an
exposed script, and `module:function` follows ADR-0058. The rule only adds roots.

The case `corpus/frameworks/tool_modules_are_roots` fails on revision 47.

MODEL_REVISION becomes `python-fastapi-dishka/48`.
