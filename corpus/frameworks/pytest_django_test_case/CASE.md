# Test cases that derive from Django and DRF test base classes

`django.test.TestCase`, `SimpleTestCase`, `TransactionTestCase`, and the Django REST framework
`APITestCase` family all derive from `unittest.TestCase`, so pytest collects their subclasses and
runs every `test_*` method, whatever the project's own `pytest` settings say about classes. The
test classes below run; the `Tool.unused` function is referenced nowhere and keeps the case from
being satisfied by weakening the whole world.
