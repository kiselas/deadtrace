# ADR-0078: A module that edits `sys.path` imports its siblings by bare name

**Status:** Accepted, 2026-10-12; model revision 61.

Scripts inside a package often run `sys.path.insert(0, SCRIPT_DIR)` and then `import console` for
the sibling `console.py`. ADR-0017 resolves bare imports beside the importer only in directories
that are not regular packages, so these imports stayed unresolved and the siblings' functions were
reported as unreached (8 reviewed findings in one cohort project).

When the importing module's source mentions `sys.path`, a bare absolute import that no earlier rule
resolved is looked up in the importer's own directory too, whether or not it is a package, if the
imported module (or, for `from X import m`, the module `X.m`) exists there. A module that does not
touch `sys.path` keeps the earlier rules, so `utils/requests.py` still does not shadow `import
requests` in ordinary modules.

The case `corpus/python/sys_path_sibling_import` fails on revision 60.

MODEL_REVISION becomes `python-fastapi-dishka/61`.
