# A private implementation of a public method

The package exports `Process`, an abstract class, and `open_process`, which returns a private
`Impl` of it. Users call `terminate` and `kill` on what `open_process` returns, so the overrides
in `Impl` run, though nothing in the project calls them. Reporting them is unsafe.

`Impl.helper` is called by nothing and stays a candidate, and so does `_Dead`, an implementation
that nothing constructs: a public method runs on an instance, and an instance of `_Dead` never
exists.
