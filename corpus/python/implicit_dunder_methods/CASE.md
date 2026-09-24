# Special methods called implicitly

`main` prints a `Money`, compares two with `==`, and puts one in a set. Python calls `__str__`,
`__eq__`, and `__hash__` for those operations; no code names them. Reporting any of them as
unreached is unsafe. `unused_control` is referenced nowhere and must stay a candidate.

Recorded as a known violation of the analysis contract (ADR-0006) and met from model
revision `python-fastapi-dishka/6` (ADR-0009).
