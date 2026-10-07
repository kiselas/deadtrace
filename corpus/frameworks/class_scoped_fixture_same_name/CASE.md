# Same-named fixtures in two classes of one module

Each class defines its own `value` fixture, and its test requests it. pytest resolves the request
to the fixture of the test's own class, so both fixtures run and `make_first` and `make_second` are
reached from tests. `unused` in the tool script is referenced nowhere.
