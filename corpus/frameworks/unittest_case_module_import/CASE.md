# TestCase imported from unittest.case

`tests/test_auth.py` imports `TestCase` from `unittest.case`, the module that defines it. `AuthTests`
does not match `python_classes`, but pytest collects every `unittest.TestCase` subclass, so its
methods run: `check` is reached only from tests. `unused` in the tool script is referenced nowhere.
