# Unittest cases that derive from TestCase through a project base

A Django sample app reruns a shared suite: `tests/accounts/tests.py` subclasses `BaseAuthTests`,
which a private module of the package defines on top of `unittest.TestCase`. Django's runner and
`unittest discover` import `tests.py` and run `AuthTests`, so the module counts as collected:
`AuthTests.token` is not a candidate, and `check` is reached only from tests. `unused` in the tool
script is referenced nowhere.
