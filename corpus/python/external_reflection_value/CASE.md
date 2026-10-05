# An external annotation allows a project subclass

`main` accepts a Path, which may be an instance of `ProjectPath`. The runtime name may be
`check`. Retrieving that bound method and calling the stored callback executes `ProjectPath.check`.
It must not be a removal candidate. The unrelated private function has no references and remains
a candidate. An annotation does not exclude subclasses. This expectation follows from Python's
attribute lookup, independently of scanner output; the target is never executed by the scanner.
