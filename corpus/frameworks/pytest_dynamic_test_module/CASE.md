# A test module that creates its tests when it runs

`test_generated.py` holds no `def test_` and no `class Test`. It builds a test class at import
time from `_cases.py`: `TestGenerated = SUITE.to_testcase(SUITE.cases(), skip=lambda t: skip_slow(t))`.
pytest imports every module that matches `python_files`, so that statement runs, and with it
`skip_slow`, which nothing else calls. The unsafe outcome is reporting it. `Suite.unused` is called
by nothing and stays a candidate; `Suite` itself is reached only from tests (`RCH004`).
