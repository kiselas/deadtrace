# Module-level `__getattr__` and `__dir__`

`_compat.py` defines `__getattr__`, which serves names that were moved, and `__dir__`, which
lists them. `_tool.py` imports the module and reads `_compat.OLD_LIMIT`, a name the module does not
define: Python calls `__getattr__` for it (PEP 562), and `dir(_compat)` calls `__dir__`. Reporting
either as unreached is unsafe. `unused` is called by nothing and stays a candidate.
