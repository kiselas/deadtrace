# An instance stored on an object from outside the project

The test sets `request.user = _MockSuperUser()` on a request that Django's `RequestFactory` built and
passes the request to the admin view, which calls `request.user.has_perm(...)` by protocol. The
stand-in's public `has_perm` is not a candidate; its private `_private` and the class `_Unused`,
which nothing instantiates, are.
