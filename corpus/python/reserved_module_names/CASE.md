# Names that a host looks up in a module

A function named `__ExtensionFactory__` is not called by any Python code: the program that loads
the module, an ISAPI host here, looks the name up. Python reserves names that begin and end with
two underscores, so such a definition is an entry point. `unused` is referenced nowhere.
