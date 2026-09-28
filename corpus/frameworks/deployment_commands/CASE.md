# Programs that deployment files start by name

The repository starts its programs outside Python:

- `docker-compose.yml` runs `uvicorn svc.profiling:app` from the service directory, in list
  form, next to a `wait_for.sh` wrapper, and `arq svc.worker.WorkerSettings` in string form;
- `svc/Dockerfile` runs `python -m svc.tasks`;
- `Procfile` runs `python tools/seed.py`, a script without a main guard;
- `svc/logging.conf` names `class: svc.logs.JsonFormatter`, which the logging configuration
  instantiates and whose `format` it calls.

Nothing in the project imports these modules. The unsafe outcome is reporting what they run:
`enable_profiling`, the arq job, the task, the seed helper, or the formatter's `format`. A
function that nothing uses is still reported.
