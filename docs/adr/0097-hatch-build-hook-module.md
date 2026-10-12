# ADR-0097: hatch_build.py is a tool module

**Status:** Accepted, 2026-10-12; model revision 80.

ADR-0066 treats files that a development tool runs by their name (`setup.py`, `noxfile.py`, Sphinx's
`docs/conf.py`, ...) as roots whose top-level functions the tool may call. Hatchling loads
`hatch_build.py` the same way: it is the default file of the custom build hook
(`[tool.hatch.build.hooks.custom]`) and of the custom metadata hook, and hatchling calls the hook
class it defines, whose methods use the module's helpers.

In the blind seventh cohort, three helpers of one project's `hatch_build.py` were reported as reached
only from tests, verdict false.

`hatch_build.py` joins the tool module names. Its helpers are not candidates, as for `setup.py`.

The case `corpus/python/hatch_build_hook` fails on revision 79.

MODEL_REVISION becomes `python-fastapi-dishka/80`.
