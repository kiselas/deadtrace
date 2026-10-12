# Modules held in a dispatch table

`tracker/cli.py` keeps two adapter modules in `LOADERS` and calls `loader.load_entries()` or the
`load_recent` that `getattr` finds on the module it reads back. The value has no known type, so the
`load_entries` and `load_recent` of either module may run: they are protected by an unknown
boundary. `_unused_helper` is named nowhere, and the `load_entries` of `_legacy.py`, a module no
container holds, is reached by nothing.
