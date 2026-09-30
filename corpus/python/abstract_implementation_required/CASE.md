# An implementation of an abstract method is required

`Cancel` cannot be created unless it defines `run`, although nothing calls `run` on it. Reporting
the method would suggest a deletion that breaks the class. `Cancel.extra` is not required by any
base and nothing calls it, so it is reported.
