# Private methods of a class handed to an unknown consumer

`main` passes `Handler` to `somelib.register`, which may call what the class offers to outside
code: `handle`, `__call__`, and the `_repr_html_` hook that display libraries look up by name. All of
them are protected by the unknown consumer. `_parse` runs because `handle` calls it. `_stale` is a
private method that no code of the class calls; the consumer has no reason to know its name, so it
is a candidate.
