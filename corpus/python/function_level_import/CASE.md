# Imports inside functions

`main` imports the `reports` module and `schedule` from `tasks` inside its body, calls
`schedule`, and calls a nested function that uses `reports.build`. Calling `main` runs
the top level of `tasks`, which calls `register_defaults`. Reporting `schedule`, `_plan`,
`register_defaults`, or `reports.build` as unreached is unsafe. `tasks.unused_task` and
`main.unused_control` are never called and must stay candidates.

Recorded as a known violation of the analysis contract (ADR-0006) and met from model
revision `python-fastapi-dishka/7` (ADR-0010).
