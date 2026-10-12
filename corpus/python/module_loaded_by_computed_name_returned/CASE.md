# A module imported by a computed name and returned

`_load_backend` imports the module that a registry names and returns it; `main` calls
`backend.build_eval_command(...)` on the result. The module may be any the computed name reaches,
so the `build_eval_command` of a project module may run and is protected. `_unused` is called by
nothing.
