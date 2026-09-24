# Class passed to external code

`main` gives the class `Point` to `ctypes` as an argument type, as rich's
`_win32_console` does with `WindowsCoordinates`. For each call, `ctypes` calls the
class method `from_param` to convert the argument, and nothing in the project names it.
Reporting `Point.from_param` as unreached is unsafe. `Unused.from_param` belongs to a class
that nothing passes anywhere and must stay a candidate.

Recorded as a known violation of the analysis contract (ADR-0006) and met from model
revision `python-fastapi-dishka/9` (ADR-0012).
