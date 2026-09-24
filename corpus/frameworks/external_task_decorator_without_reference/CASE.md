# Task registered by an unmodeled framework and never referenced

`nightly_cleanup` is registered with `@app.task` on a Celery application, which Deadtrace does not
model, and no Python code refers to it again. A scheduler or another service can still invoke it by
its registered name. Reporting it as unreached is unsafe. A guard local to the decorated function and
a weakened world are both acceptable outcomes, so this case has no control candidate.

Recorded as a known violation of the analysis contract (ADR-0006) and met from model
revision `python-fastapi-dishka/5` (ADR-0008).
