# Callable passed to a project function

This is the seed case `fixtures/cases/escaped-callback-helper` with a configured world, so that its
expectation is checked semantically instead of only lexically. `register_external` stands for a
registration function whose body does not call the callable it receives; the callable can still run
later through whatever holds it. The seed states the expectation: `callback` and `callback_helper`
are protected, and protecting only the callback declaration is unsafe.

Recorded as a known violation of the analysis contract (ADR-0006) and met from model
revision `python-fastapi-dishka/5` (ADR-0008).
