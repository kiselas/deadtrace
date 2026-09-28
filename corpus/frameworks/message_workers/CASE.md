# Message and task workers

`run_faststream.py` builds a FastStream application around a broker that includes a router whose
subscribers handle queue messages; `run_scheduler.py` builds a taskiq scheduler, run by
`taskiq scheduler`, whose broker runs an event hook at startup; `worker.py` defines the settings
class that the `arq` command reads, with its task and cron functions, annotated or not, and its
startup hook. Each is started by its own command, not imported. A taskiq worker started as
`taskiq worker module:broker` is not an application root.

The unsafe outcome is reporting the subscriber, the startup hooks, or the arq tasks as
unreached, or as reached only from tests, because no application world roots these modules. A
function that nothing uses is still reported.
