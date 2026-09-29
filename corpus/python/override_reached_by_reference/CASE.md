# An override reached through a method passed as a value

`Handler.run` schedules `self.first` for a project function that calls it, and wraps
`self.second` in `functools.partial`. The instance is a `Plugin`, which overrides both methods,
so the overrides run, though nothing calls them by name. The unsafe outcome is reporting them.
`Plugin.unused` is called by nothing and stays a candidate.
`Sibling` derives from the same base as `Handler` but not from `Handler`, so `self.first` in
`Handler.run` never reaches its `first`, which stays a candidate.
