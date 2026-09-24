# Base initializer called through `super()`

`main` constructs `Child`, whose initializer calls `super().__init__()`, which runs
`Base.__init__`. `Base` is also the base of the constructed class. Reporting either one as
unreached is unsafe. `unused_control` is referenced nowhere and must stay a candidate.

Recorded as a known violation of the analysis contract (ADR-0006) and met from model
revision `python-fastapi-dishka/5` (ADR-0008).
