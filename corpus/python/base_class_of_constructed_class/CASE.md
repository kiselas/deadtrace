# Base class of a constructed class

`main` constructs `Child` and calls `describe` on the instance. `Child` defines nothing itself:
creating the class evaluates its base `Base`, and the call runs the inherited `Base.describe`.
Deleting `Base` breaks `Child`, and deleting `Base.describe` breaks the call, so reporting either
one as unreached is unsafe. `unused_control` is referenced nowhere and must stay a candidate.

Recorded as a known violation of the analysis contract (ADR-0006) and met from model
revision `python-fastapi-dishka/5` (ADR-0008).
