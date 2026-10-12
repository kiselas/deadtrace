# A class statement expected to raise

`test_invalid` declares `_Invalid` inside `pytest.raises(SetupError)`: the base class rejects the
declaration when the statement runs, and that is what the test checks. The class is used by its own
creation and is not a candidate. `_Unused` in `test_other` is declared and never used.
