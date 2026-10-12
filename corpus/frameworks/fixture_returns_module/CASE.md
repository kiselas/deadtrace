# A fixture that returns a module

The session fixture `helpers` imports the module `tests.helpers.helpers` inside its body and returns
it; `test_dedent` receives it as `helpers` and calls `helpers.dedent(...)`. The module is a value, so
the name dispatch of `helpers.dedent` reaches its `dedent`. `never_used` is called by nothing.
