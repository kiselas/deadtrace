# Dataclass `__post_init__`

`@dataclass` generates an `__init__` that calls `__post_init__` after assigning the fields, so
constructing `Order` runs it. Reporting it as unreached is unsafe. `unused_control` is referenced
nowhere and must stay a candidate.

Recorded as a known violation of the analysis contract (ADR-0006) and met from model
revision `python-fastapi-dishka/6` (ADR-0009).
