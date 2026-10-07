# Test file named only by a Makefile command

`_checks.py` does not match pytest's `python_files`, but `make test` runs `pytest _checks.py`, and pytest
collects a file given as an argument whatever its name. The file counts as collected: `test_price`
and `TestPrice` are test code, not candidates, even though the file is outside a test directory. `unused` in the tool script is referenced nowhere.
