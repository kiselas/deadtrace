# ADR-0068: A module nobody imports that calls at top level is a script

**Status:** Accepted, 2026-10-07; model revision 50.

The scripts world (ADR-0012) started `__main__` modules and modules with a main guard. Examples,
samples and tutorials often end with a bare call instead: `setup(env)`, `asyncio.run(main())`,
`print(run())`. Nothing imports them; they exist to be run. Their functions, and the project code
they call, were reported as unreached: 37 reviewed findings in three cohorts were of this form.

A module is now also a script root when nothing in the project imports it (directly or as a
package of an imported module), it is not a package `__init__`, a `conftest.py` or a test file,
no earlier world or deployment command already starts it, it imports nothing from `alembic`
(whose environment and revisions belong to the migrations world), and its top level has an
expression statement that is a call or an `await`. Its provenance is `top_level_script`. Only the
module body is a root: functions the script never calls stay findings.

Pricing on the reviewed findings: modules matching the rule hold 37 false and at most 11 true
findings; most of those true ones are functions the script does not call, which stay reported.
A module run by file name (ADR-0017) that matches is now a resolved root rather than a conservative
one, so `corpus/python/script_run_by_file_name` no longer carries `DT2002`.

The case `corpus/python/unguarded_example_script` fails on revision 49.

MODEL_REVISION becomes `python-fastapi-dishka/50`.
