# Django calls inherited database fixture hooks

Django database test cases invoke `_fixture_setup` during pre-setup and
`_fixture_teardown` during post-teardown. Python method lookup selects overrides
from project mixins listed before the external Django base. Both instance methods
and the classmethod setup form are framework callbacks, despite their private names.
The two used cases inherit these overrides from another module.

The unrelated private helper, hooks of an unused case, an overridden setup method,
and fixture-named methods mixed into plain unittest.TestCase have no caller.
They remain candidates. This prevents protecting arbitrary private mixin methods
or all definitions with the same name.

Independent contract: [Django 5.2 testcases source](https://github.com/django/django/blob/stable/5.2.x/django/test/testcases.py),
TransactionTestCase._pre_setup and _post_teardown. Target code is static test data.
