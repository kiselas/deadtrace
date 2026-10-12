# getattr with a known name on a value of unknown type

`run` receives `llm` as a parameter and calls `getattr(llm, "saveState")("model")` and
`getattr(llm, f"load_{kind}")()`. These are the calls `llm.saveState(...)` and `llm.load_<kind>()`:
any project method of that name, or starting with `load_`, may run, so `saveState` and `load_cache`
are protected by name. `_unused` and the module-level `helper` fit neither name and are reached by
nothing.
