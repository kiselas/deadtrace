# Unittest cases in the `__init__.py` of a tests package

Django's runner and `unittest discover` import a `tests` package and run the cases it defines, though
`__init__.py` matches no pytest pattern. The module counts as collected: `AuthTest`, its test, and
`check` are not candidates. `unused` in the tool script is referenced nowhere.
