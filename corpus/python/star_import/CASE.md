# Star import

`main` imports every public name of `helpers` with `from helpers import *` and calls
`greet`, which calls `_format`. Reporting either as unreached is unsafe.
`helpers.unused_helper` is bound by the import but never called, so it must stay a
candidate.

Recorded as a known violation of the analysis contract (ADR-0006) and met from model
revision `python-fastapi-dishka/7` (ADR-0010).
