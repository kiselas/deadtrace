# A plugin that addopts loads

`addopts = -p tests.plugin_fixtures` makes pytest import `plugin_fixtures` before collection, and its
fixtures serve every test. A test that requests `clock` therefore resolves it, and the fixture is
used.
