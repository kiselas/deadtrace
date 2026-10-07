# ADR-0063: Poetry, flit, and `setup.cfg` entry points

**Status:** Accepted, 2026-10-07; model revision 45.

Entry points (ADR-0009) were read only from PEP 621 `[project]`. Projects that declare them
elsewhere had no entry-point worlds: commands and pytest plugins were unreached. In one cohort
project, a package's pytest plugin registered under `[tool.poetry.plugins."pytest11"]` made 20 of
26 findings false.

The reader now also takes, as data and without invoking a build backend:

- Poetry: `[tool.poetry.scripts]` (group `console_scripts`) and `[tool.poetry.plugins.<group>]`;
- flit: `[tool.flit.scripts]` and `[tool.flit.entrypoints.<group>]`;
- `setup.cfg`: `[options.entry_points]`, one `name = module:object` per line.

Values that are not an object reference (Poetry's table form, for example) are skipped silently,
since these formats are not ours to validate; PEP 621 keeps its `DT4101` limitations. Entry points
are production roots, so the change only removes findings. `setup.py` is not read: it is code.

The cases `poetry_scripts_entry_point`, `flit_scripts_entry_point`, and `setup_cfg_entry_point`
fail on revision 44.

MODEL_REVISION becomes `python-fastapi-dishka/45`.
