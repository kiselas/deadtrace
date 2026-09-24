# Method on the result of an unannotated factory

`make_repository` has no return annotation and returns a `Repository`. `main` calls `fetch` on the
result. Without a type for the receiver the call target is unknown, but it may be
`Repository.fetch`, which is the only method of that name in the project. Reporting it as unreached
is unsafe. `unused_control` is referenced nowhere and must stay a candidate.

Recorded as a known violation of the analysis contract (ADR-0006) and met from model
revision `python-fastapi-dishka/5` (ADR-0008).
