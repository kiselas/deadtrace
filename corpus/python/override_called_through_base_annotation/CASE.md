# Override called through a base-class annotation

`make_notifier` is annotated to return `Notifier` but returns an `EmailNotifier`. The call
`notifier.send(...)` therefore runs `EmailNotifier.send`, the override, not only the method the
annotation names. `Notifier` is also the base of the constructed class. Reporting the override or
the base as unreached is unsafe. `unused_control` is referenced nowhere and must stay a candidate.

Recorded as a known violation of the analysis contract (ADR-0006) and met from model
revision `python-fastapi-dishka/5` (ADR-0008).
