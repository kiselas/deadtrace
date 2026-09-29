# A script that runs its own test cases

`unittest.main()` under the `__main__` guard collects the `TestCase` classes of the module and runs
their tests, so `Checks` and its methods are used although no name refers to them. `unused` is
referenced nowhere.
