# A mixin that calls a method its subclass defines

`Commands.commit` calls `self._build_header` and `self.provided_elsewhere`, and `Commands` defines
neither. `Graph(Commands, Extra)` defines the first and inherits the second from `Extra`, so both
run when `Graph().commit()` does. Reporting them is unsafe. `Stranger` has methods of the same
names but is no subclass of `Commands`, so its `_build_header` stays a candidate, as does
`Graph.unused`.
