# A name used before it is redefined

The first `Form` is instantiated before the second `class Form` statement rebinds the name, so both
classes are used. `use` calls `helper` only when it runs, after the second `def helper` has rebound
the name, so the first `helper` is never called and stays a candidate. `unused` is referenced nowhere.
