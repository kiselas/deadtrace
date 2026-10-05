# A library whose test suite builds an application

The package `lib` is a library: `Api` and its public method are what its users call. Its test
suite builds a Flask application in `tests/conftest.py` as a fixture. That application is a test
fixture, not a deployed program, so it must not become a production world and hide the library's
public API: `Api` and `Api.register` stay reached by the library world. `_unused` is private and
referenced nowhere, which keeps the case from being satisfied by weakening the whole world.
