# Project decorator applied without parentheses

`@log_calls` above `decorated` calls `log_calls(decorated)` when the module is imported, and the
name `decorated` then refers to the returned `wrapper`, which `main` calls. Deleting `log_calls` or
`wrapper` breaks the program. Reporting either one as unreached is unsafe. `unused_control` is
referenced nowhere and must stay a candidate.

Recorded as a known violation of the analysis contract (ADR-0006) and met from model
revision `python-fastapi-dishka/5` (ADR-0008).
