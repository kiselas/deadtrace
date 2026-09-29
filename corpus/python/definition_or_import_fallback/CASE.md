# A definition in one branch, an import in another

`workers` binds `cpu_count` three ways: a nested `def` when `sched_getaffinity` exists, and two
imports of the same name when it does not. The call `cpu_count()` runs whichever was bound, so the
nested definition is not unreached even though the imports come from outside the project.
`unused` is called by nothing and stays a candidate.
