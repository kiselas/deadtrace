# Docstring examples run by --doctest-modules

`addopts = "--doctest-modules"` makes pytest run the example in `discounted`'s docstring, which calls
`_round`. `total`'s example imports `sample_basket` from `tests/examples.py` and calls it, so that
helper is reached too. `_round` is reached from the tests world, like a helper a test calls. `_never_documented`
is called nowhere.
