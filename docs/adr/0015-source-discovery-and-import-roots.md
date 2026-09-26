# ADR-0015: Source discovery and import roots

**Status:** Accepted, 2026-09-26.

## Context

The audit of 2026-09-26 ran `deadtrace scan .` without configuration on six local checkouts,
five of them private applications, and on Deadtrace itself. The source universe held every `.py`
file below the scan path except seven fixed directory names. Four checkouts kept a virtual
environment named `venv`: in one FastAPI and Dishka service it made 3,707 of 4,318 files and
1.5 of 1.6 million lines, and the scan took 341 seconds instead of 11.6; installed packages rooted
worlds of their own (`production:typer:venv.Lib.site-packages.typer.cli.app`). On Deadtrace's own
checkout, `.pytest-tmp` contributed seven unparsable test inputs that made every world partial.

Module names dropped a leading `src/` from the path. One service puts the checkout root on the
path and imports `src` itself (`from src.api.routes import router`):
those imports matched no module, its included routers were reported as unpublished, and nothing
warned. A benchmark script imported its sibling module (`import lab`), which Python finds because
it puts a script's directory on the path; that import matched no module either, so the functions
the script calls were reported as unreached.

## Decision

1. **Skipped directories.** Below the scan path, discovery skips a directory whose name starts
   with a dot, `__pycache__`, `__pypackages__`, `node_modules`, and `site-packages`, and a
   directory that contains `pyvenv.cfg` or `conda-meta`. None of them can hold importable project
   code: a dot cannot start a package name, and the others hold installed distributions or other
   tools' files. The scan path itself is never skipped. Other directories, including ones whose
   names are not identifiers, stay in the universe, because their scripts run when invoked by
   path.
2. **Reporting.** Skipped directories are part of the snapshot and of its stability check, are
   listed in the JSON report as `source_universe.skipped_directories`, and are named in the text
   report except hidden ones and `__pycache__`. The field is additive; schema 1 is unchanged.
3. **`src` as a package.** When a file lies under `src/` and project code imports `src` or
   `src.*` absolutely, `src` is part of the module names below it. Otherwise it is a source root
   and left out, as before.
4. **Import roots.** An absolute import whose first part is no top-level project module is tried
   against the directories of the importer that are not regular packages, innermost first,
   never resolving to the importer itself. Python puts a script's directory on the path, and
   pytest's default import mode does the same for test modules outside packages. A match only
   adds code that may run; an import of an installed distribution that shares a sibling's name
   is taken for the sibling.

## Consequences

- The service's scan falls from 341 to about 6 seconds, and installed packages no longer root
  worlds or protect project code. `tests/test_inventory.py` covers each kind of skipped
  directory and an explicit scan of a `site-packages` directory.
- `corpus/frameworks/fastapi_src_package_imports` records the `src` package case; unit tests in
  `tests/test_import_roots_and_dispatch.py` cover sibling imports, a package module that must not
  see its sibling `json.py` as the standard library, and a `celery.py` that must not import
  itself.
- A file loaded from an arbitrary directory with `sys.path.insert` that is no ancestor of the
  importer is still not found; configured roots or keep contracts cover it.
- Changing the source universe changes the source digest, so reports of a checkout with a
  skipped directory are `partially_comparable` with earlier ones.
