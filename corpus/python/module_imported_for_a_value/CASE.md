# Module imported for a value

`main` imports `settings`, a value rather than a function or class, from `config`.
Importing it runs the top level of `config`, which calls `load`. Reporting `load` as
unreached is unsafe. `config.unused_loader` and `main.unused_control` are never called and
must stay candidates.

Recorded as a known violation of the analysis contract (ADR-0006) and met from model
revision `python-fastapi-dishka/7` (ADR-0010).
