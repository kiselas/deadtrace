# A package re-exports its API from a pure-Python module or a compiled one

`md/__init__.py` imports `MultiDict` and `getversion` from `._impl` when extensions are off and
from `._ext`, a compiled module with no source, otherwise. The package's API is the project's
definitions whichever branch ran, so `MultiDict`, its public method `add`, and `getversion` are used.
`MultiDict._unused` and `_unused_helper` are private and referenced nowhere.
