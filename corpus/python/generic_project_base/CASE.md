# A generic project base

`UserRepo` derives from the project class `BaseRepo` through the subscription `BaseRepo[int]`.
`main` calls the inherited `get`, which calls `self._load()`: the override in `UserRepo` runs.
`UserRepo._never` and `BaseRepo._base_only_unused` are called by nothing. `BaseRepo` is a project
class, so no external base can call the methods of `UserRepo` by name.
