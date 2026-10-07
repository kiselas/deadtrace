# ADR-0065: A nested package imported by its own name

**Status:** Accepted, 2026-10-07; model revision 47.

Projects make a nested package importable by its own name: `src/__init__.py` runs
`sys.path.insert(0, SRC_DIR)` and imports `core.init_app`; a monorepo imports `os_ai_core` from
`packages/core/src/os_ai_core`; Django test projects import `test_app.models` with `tests/` on the
path. ADR-0017 and ADR-0022 resolve sibling directories and editable distributions, but skip
directories that are regular packages, so these imports stayed unresolved. In one cohort project
the whole application behind a factory was lost: 66 findings, most of them false; in another a
monorepo package's functions were unreached.

When an absolute import's first part is no top-level project name and no earlier rule resolved
it, the shallowest project package with that last name is taken, if it is unique at that depth and
the imported module, or for `from X import m` the module `X.m`, exists under it. A plain module is
never taken (`utils/requests.py` does not shadow `import requests`), and a directory that lacks the
imported module is not either (`app/alembic/` does not shadow `from alembic import context`).
Resolving an import adds edges to project code; it cannot add a finding.

The case `corpus/frameworks/nested_package_import_root` fails on revision 46.

MODEL_REVISION becomes `python-fastapi-dishka/47`.
