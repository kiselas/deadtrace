# A method called on a typing.cast value

`Artifact.build` calls `cast(ArchiveStrategy, self.archive)._build()`, and `build_quoted` does the
same with the class named in a string. `cast` returns its second argument unchanged and tells the
reader its type, so `_build` of `ArchiveStrategy` runs. `_unused` is called by nothing.
