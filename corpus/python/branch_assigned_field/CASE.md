# Fields assigned instances of different classes

A call on a `self` field runs the method of whichever instance the field holds, so a field has a
single type only when every assignment to it agrees:

- `Layout` declares `self.strategy: Strategy` and assigns `Wide()` or `Narrow()` by a branch.
- `Switcher` assigns `Fast()` in `__init__` and `Slow()` in `reset`.
- `Client` assigns `transport or default_transport()`, whose class is not known, in `__init__`
  and `FakeTransport()` in `use_fake`; `OfflineClient`, a subclass, assigns `LocalTransport()`,
  and the program assigns `client.backup = TapeBackup()` from outside the class.
- `Store` declares `self.cache: RedisCache` but assigns `NullCache()` or `RedisCache()`.

The unsafe outcome is reporting a method of one of those classes because the last assignment,
the assignments of one method, of the class without its subclasses, or a contradicted
annotation gave the field its type. A function that nothing calls is still reported.
