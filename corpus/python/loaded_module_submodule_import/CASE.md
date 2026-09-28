# Importing a submodule of a module that is loaded already

`load_tables` runs `importlib.import_module(f"{obj.__module__}.tables")`. The name starts with
the module of an object that exists, so that module is loaded, and the import runs its
`tables` submodule. `_shop` is imported and its `Order` passed in, so `_shop.tables` may run;
nothing imports `_legacy`, so no object has it as its module and `_legacy.tables` cannot run,
as long as no class reassigns its `__module__`. `load_plugin_tables` passes the `__name__` of
the namespace package `_plugins._shop`, a directory without `__init__.py`, whose `tables`
submodule has no module to wait for.

The unsafe outcome is reporting `_shop.tables.build` or `_plugins._shop.tables.build`, which run
when their submodule is imported. `_legacy.tables.build` is reported instead of being kept by
every computed import.
