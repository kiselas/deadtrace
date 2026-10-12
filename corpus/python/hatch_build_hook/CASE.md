# A hatchling build hook

`pyproject.toml` enables `[tool.hatch.build.hooks.custom]`, and hatchling loads `hatch_build.py` by
its file name during a build and calls the hook class it defines. The module is a tool module, like
`setup.py`: its top-level functions are not candidates. `_dead` in the application is called by
nothing.
