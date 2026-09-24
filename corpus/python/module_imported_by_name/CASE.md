# Modules imported by name

`main` imports `plugins.alpha` with `importlib.import_module("plugins.alpha")` and one more plugin
through an f-string, `f"plugins.{name}"`. Importing a module runs its top level, which calls
`setup` in each plugin. Reporting either `setup` as unreached is unsafe. `tools.unused.helper`
lives outside the `plugins.` prefix and nothing imports it, so it must stay a candidate, as must
`unused_control`.

Recorded as a known violation of the analysis contract (ADR-0006) and met from model
revision `python-fastapi-dishka/6` (ADR-0009).
