# Task registered by an unmodeled framework and queued through an attribute

`send_email` is registered with `@app.task` on a Celery application, which Deadtrace does not
model, and `main` queues it with `send_email.delay(...)`. A worker process runs it. Reporting it as
unreached is unsafe. A guard local to the decorated function and a weakened world are both
acceptable outcomes, so this case has no control candidate.

Recorded as a known violation of the analysis contract (ADR-0006) and met from model
revision `python-fastapi-dishka/5` (ADR-0008).
