# A program with a main guard in a test directory

`tests/fuzz.py` is run as `python tests/fuzz.py`, with a main guard, beside `tests/test_basic.py`.
pytest collects only `test_*.py`, so the fuzz script is not a test module, and it is not a
library. The directory name does not make a program a test: the main guard makes it a script root.
Reporting `main` or `target` is unsafe. `dead` is called by nothing and stays a candidate.
