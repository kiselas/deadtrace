# vars() of an instance and of a class

`main` passes `vars(_build_parser().parse_args())` on as keyword arguments. `vars(obj)` is the
instance's `__dict__`: its own attributes, not the methods of any class, so `_Store.save`, which
nothing calls, stays a candidate. `vars(_Registry)` lists the namespace of the class itself, whose
members are protected.
