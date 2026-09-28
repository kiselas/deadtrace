# Classes created for what their creation runs

`Registered.__init_subclass__` records every subclass in a registry when its class statement
runs. `_plugins.py` defines `CsvExport(Registered)`, which nothing names: importing the module
registers it, and the program looks exporters up in the registry. A function defines
`Local(Registered)` in its body to register a class while it runs.

The unsafe outcome is reporting `CsvExport` or `Local`, whose class statements run the hook
where they stand. A class without such a hook that nothing uses is still reported.
