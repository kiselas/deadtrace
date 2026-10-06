# Test modules named for `unittest discover`

`tests/tests_auth.py` does not match pytest's `test_*.py`, but `python -m unittest discover`
collects it through its default `test*.py` pattern, and the module defines a `unittest.TestCase`.
Whether this project runs unittest or pytest cannot be known statically, so the module counts as
collected: `AuthTest`, its test method, and the `check` helper it calls are not candidates.
`unused` in the tool script is referenced nowhere.
