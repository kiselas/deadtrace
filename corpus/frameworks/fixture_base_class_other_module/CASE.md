# Fixture defined by a base class in another module

`TestCart` inherits the `items` fixture from `BaseCartTest` in `tests/base.py`. The request resolves,
the tests world is complete, and `total` is reached from tests. `unused` is referenced nowhere.
