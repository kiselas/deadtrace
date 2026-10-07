# A nested package imported by its own name

`_svc/main.py` puts its own directory on `sys.path` and imports `core.tools`, which is the project
package `_svc/core`. Exactly one project package is named `core`, so the import resolves to it:
`helper` is reached; `unused` is referenced nowhere.
