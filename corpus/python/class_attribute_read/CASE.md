# Reading an attribute of a class does not call its methods

`Settings.limit` and `Kind.A.value` need the classes, but they read a class attribute and an enum
member. Neither is a method, so a method of the class that nothing calls is still unused.
