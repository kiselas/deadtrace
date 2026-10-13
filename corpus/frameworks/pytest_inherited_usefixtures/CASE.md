# Inherited usefixtures marks

Pytest includes class marks from the class MRO when it collects a test method. A usefixtures
mark on a project base therefore requests its fixture for a subclass's test, even when the base
lives in another module and imports pytest under an alias. The intermediate class also inherits
the mark. These fixture functions may run in the tests world.

The unused fixture belongs to a marked class with no collected subclass or test. Its name must
remain a candidate: merely declaring a marked base does not request a fixture.
