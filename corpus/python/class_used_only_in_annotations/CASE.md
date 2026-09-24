# Class used only in an annotation

`configure` annotates its parameter with `Settings`. Without `from __future__ import annotations`,
the annotation is evaluated when the `def` statement runs, so deleting `Settings` makes importing
the module fail. Reporting `Settings` as unreached is unsafe. `unused_control` is referenced nowhere
and must stay a candidate.

Recorded as a known violation of the analysis contract (ADR-0006) and met from model
revision `python-fastapi-dishka/5` (ADR-0008).
