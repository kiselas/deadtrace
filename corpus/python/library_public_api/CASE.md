# Library public API

`textkit` has no application, entry point, or script, so the automatic
`production:library` world roots its public API: the top-level names of public modules that
do not start with an underscore, the names `__all__` adds, the names a package imports, and
the public methods of API classes. The package re-exports `parse` from its private module
`_impl`; `models.Document.render` is a public method; `utils` lists `slugify` in `__all__`,
adds the underscored `_legacy_slugify` with `+=`, and leaves out `normalize`, which callers
still reach as `textkit.utils.normalize`. All of these and what they call are live.
`_impl.not_reexported` is public by name but lives in a private module and is not
re-exported, and the other underscored helpers are unused and unlisted, so they stay
candidates.
