# Function reference in a registry

`handle_create` and `handle_delete` are never called by name. They are stored in the module-level
`HANDLERS` dictionary, and `dispatch`, which `main` calls, invokes whatever the dictionary holds.
Either handler may run, so reporting either one as unreached is unsafe. Whether they become resolved
or conservative is a modeling choice; the expectation is only that neither becomes a candidate.
`unused_control` is referenced nowhere and must stay a candidate, so the case cannot be satisfied by
weakening the whole world.

Recorded as a known violation of the analysis contract (ADR-0006) and met from model
revision `python-fastapi-dishka/5` (ADR-0008).
