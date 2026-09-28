# pytest plugins named through a regular `src` package

`src/__init__.py` makes `src` a regular package, and `pythonpath = ["src"]` lets the code import
`shop.orders`. The root `conftest.py` loads its fixtures with
`pytest_plugins = ["src.shop.tests.fixtures"]`; in its default `prepend` import mode pytest
imports that name from the root, which it puts on `sys.path` for the root conftest, so the module is a project plugin whatever its name
under its import root.

The unsafe outcome is taking the name for an installed plugin, leaving `order` unresolved and
the tests world partial, or reporting the fixture. A fixture nothing requests is still reported.
