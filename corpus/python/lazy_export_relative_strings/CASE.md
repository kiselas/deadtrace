# A lazy export table with relative paths

A package that exports names lazily maps each name to `".module:attribute"` in a dictionary, and
imports the module when the name is first read. The string is a relative reference to the target,
as an import would be. `unused` is referenced nowhere.
