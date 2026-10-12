# A metaclass method calls members of the class it built

`TypeMeta.lookups` is a property of the metaclass; `NumberType.lookups` runs it with `cls` bound to
`NumberType`, and `cls._lookups()` calls the class's own `_lookups`. The metaclass defines no
`_lookups`, so the call may reach the `_lookups` of any class built with it: both are protected.
`NumberType._unused` is called by nothing.
