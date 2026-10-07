# Test file named only by a Makefile command

`checks.py` does not match pytest's `python_files`, but `make test` runs `pytest checks.py`, and pytest
collects a file given as an argument whatever its name. The file counts as collected: `test_price`
is not a candidate. `unused` in the tool script is referenced nowhere.
