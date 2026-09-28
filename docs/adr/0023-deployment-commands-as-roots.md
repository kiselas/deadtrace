# ADR-0023: Programs that deployment files start are roots (model revision 16)

**Status:** Accepted, 2026-09-28.

## Context

The fifth field pass (ADR-0022) left seven sampled monorepo findings that run only through
roots the analyzer did not read, and the single-service projects had more of the same kind:

- a Compose service runs `uvicorn svc.profiling:app`, an alternative application module that
  wraps the main one with a profiler; nothing imports it, so its setup functions were reported;
- `arq svc.worker.WorkerSettings`, `taskiq worker svc.broker:broker`, and
  `faststream run svc.app:app` in Compose files or Dockerfiles start workers whose modules no
  Python code imports;
- `python -m svc.tasks` in a Dockerfile, `python tools/seed.py` in a `Procfile`, a shell script
  running `python3.12 load_test.py`, and `locust -f loadtest/locustfile.py` in a Makefile run
  modules without a main guard;
- a logging configuration (`class: svc.logs.JsonFormatter`, or `()` for a factory) names a
  formatter class that `logging.config` instantiates and whose `format` the logging machinery
  calls.

Declaring each in `[[tool.deadtrace.worlds]]` or `[[tool.deadtrace.keep]]` works, but a
zero-configuration scan of such a project reports code that runs.

## Decision

1. **Reading.** Deployment files below the scan root are read as text of at most 1 MiB, never
   executed, with the source discovery's directory skips and the configured `exclude` globs;
   symlinks are skipped. Command files are Compose files, `Dockerfile*` and `Containerfile*`,
   `Procfile`, Makefiles, `justfile`, shell scripts, `*.conf` and `*.ini` (supervisord programs
   and `tox.ini`), systemd units, `.gitlab-ci.yml`, `app.yaml`, `fly.toml`, and
   `pyproject.toml` task tables. Logging configurations are `*.conf`, `*.ini`, `*.cfg`, YAML,
   JSON, and TOML files whose name contains `log`, or that a server's `--log-config` names; other
   data files are not read.
2. **Statements.** Comment lines are dropped. A command ends at a shell separator, attached or
   not, and at a line that starts a statement: an unindented line, or an indented key such as
   `image:`; an indented line or one after a trailing backslash continues it, as folded YAML and
   flow lists do, and a Dockerfile `CMD` right after `ENTRYPOINT` continues it. A
   `key=program` token, as `command=python` in supervisord or `ExecStart=` in systemd, is the
   program.
3. **Commands.** Options are taken to consume the next argument unless it is an option, and a
   target that follows a flag is still found among the values:
   - the servers `uvicorn`, `gunicorn`, `hypercorn`, `daphne`, and `granian` run the first
     positional `module:attribute`, or the first such option value other than a bind or config
     value such as `unix:app.sock`; a bare module is `module:application` for gunicorn and
     `module:app` for hypercorn. `-c python:mod` and `-c file.py`, and `gunicorn.conf.py` when
     gunicorn has no `-c`, are modules the server reads by name;
   - `faststream`, `taskiq`, `arq`, `dramatiq`, and `huey_consumer` run every positional target
     after a subcommand, since dramatiq and taskiq import every module listed; `taskiq`
     `--fs-discover` imports the modules named by `--tasks-pattern`, `tasks` by default;
   - `celery -A`, and `python`, `python3.12`, or a `$(PYTHON)` variable with interpreter
     options such as `-u` or `-X dev` before `-m module` or `script.py`;
   - `locust -f locustfile.py`, a module locust reads by name.
   A configuration names an object through a `class`, `()`, `factory`, `format_class`, or
   `handler_class` key whose value is a dotted name.
4. **Matching.** A dotted name names the project module of that name, or a module whose name
   ends with it after a prefix that is a directory and no regular package, since a service runs
   from its own directory: `svc.main` is also `services.svc.main`, but not `pkg.config.main`.
   A name starting with a standard-library module or a tool run by `python -m`, as
   `logging.handlers.X` or `pip`, names only a project module of exactly that name. When modules
   below the directory of the file naming them match, only they do, so `main:app` in
   `backend/Dockerfile` is `backend/main.py` and not a `main.py` beside `backend/`. The longest
   prefix that matches a module is the module, and the rest names the longest definition path
   that exists, as `Builder.build`. A script path is resolved beside the file naming it and from
   the root, dropping leading directories of an absolute container path such as
   `/app/tools/seed.py`; a path of two or more parts also matches as a path suffix, and a bare
   file name only beside the file or at the root. A name that matches nothing adds nothing.
5. **The world** `production:commands` roots the named modules and definitions. A configured
   object is instantiated by the program that reads the configuration, which may call any of its
   methods, and a module read by name, as gunicorn hooks or locust users, has its top-level
   definitions used by the program; those definitions and their methods are conservative,
   retained roots. Each root carries the provenance `deployment_command` with the file and the
   name. The capability is `deployment.commands`, revision 1. Like the other automatic worlds
   (ADR-0011), configured worlds replace it; `production:migrations` stays a world of its own
   (ADR-0022), and a configured world of that id is rejected.

`MODEL_REVISION` becomes `python-fastapi-dishka/16`. The reading has its own timing stage,
`frontend.deployment`.

## Consequences

- The trust boundary is unchanged: target files are read, not imported or executed, and the
  scanner does not use the network. Text that looks like a command only adds roots, so a
  misread file can hide findings but not create them.
- On the monorepo of ADR-0022, the alternative profiling applications of four services, a load
  test script, and a logging formatter are no longer reported; the single-service projects of
  the earlier passes report the same findings as before.
- An independent review of the first version found targets taken from option values
  (`--bind unix:app.sock`, `arq --watch svc`), missed supervisord and systemd `key=program`
  commands, interpreter options, and absolute container paths, locust users still reported, and
  JSON data files and commented commands protecting code; decisions 1–4 are the corrected rules,
  and `tests/test_deployment.py` and `tests/test_frameworks.py` pin them.
- Not read: Kubernetes manifests and Helm templates, `.devcontainer/` and other dot
  directories, shell defaults such as `${MODULE:-svc.tasks}`, Hydra `_target_` keys, and a test
  suite run by explicit paths. A root-level Compose file naming `main:app` for services that
  each hold a `main.py` roots all of them, since the service a `build` context selects is not
  read. `[[tool.deadtrace.worlds]]` and `[[tool.deadtrace.keep]]` declare what is missed.
- `corpus/frameworks/deployment_commands` fails on revision 15.
