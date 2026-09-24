# Class of a called static method

`main` calls `Tools.helper()`. The call goes through the class, so deleting `Tools` breaks it even
though `Tools` is never constructed. Reporting `Tools` as unreached is unsafe. `unused_control` is
referenced nowhere and must stay a candidate.

Recorded as a known violation of the analysis contract (ADR-0006) and met from model
revision `python-fastapi-dishka/5` (ADR-0008).
