# Class statements and conftest code that pytest runs

A test defines a class with a project metaclass inside the test to check what the metaclass
does when the class is created. `tests/conftest.py` calls a helper at its top level, which runs
when pytest imports the conftest.

The unsafe outcome is reporting the local class or the helper, whose code runs whenever the test
suite runs. A helper that nothing calls is still reported.
