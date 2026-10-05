# Reflection selects the exported name, not the definition's name

`api` binds `run` to `worker.work` using an import alias. Retrieving `api.run` with getattr and
calling the stored value executes `worker.work`, although that definition is not named `run`.
It must be protected. The unrelated `worker.idle` has no reference and remains a candidate.
These expectations are independently evident from Python imports and attribute lookup, without
running the target or consulting the scanner's output.
