# Returned function reference

`select_operation` returns `compute` without calling it, and `main` calls the returned value.
`compute` runs whenever `main` does, so reporting it as unreached is unsafe. `unused_control` is
referenced nowhere and must stay a candidate.

Recorded as a known violation of the analysis contract (ADR-0006) and met from model
revision `python-fastapi-dishka/5` (ADR-0008).
