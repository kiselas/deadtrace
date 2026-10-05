# A unittest base class behind an alias

`tests/util.py` says `TestCase = unittest.TestCase`, and a test module derives from that name.
pytest collects every `unittest.TestCase` subclass whatever it is called, so `Suite` and its
methods run. `unused` is referenced nowhere.
