# ADR-0014: The frameworks of a configured world are declarative

**Status:** Accepted, 2026-09-24.

## Context

`[[tool.deadtrace.worlds]]` accepts a `frameworks` list, validated against five names: `python`,
`fastapi`, `dishka`, `pytest`, and `pydantic`. Nothing reads the list: every capability has always
applied to every world. Since ADR-0011 and ADR-0013, Django, Celery, Flask, and seven more
frameworks shape the analysis, yet a world that listed `django` failed to load.

Making the list select capabilities would let a world switch one off. A capability only adds edges,
retention, and guards that code may need; without it, code the framework runs could be reported as
unreached, which the analysis contract forbids.

## Decision

The list is declarative. It records which frameworks the world is expected to use; every capability
still applies to every world. The accepted names are the families the analysis models: `python`,
`fastapi`, `dishka`, `pydantic`, `pytest`, `django`, and the ten frameworks whose applications root
automatic worlds, `aiohttp`, `bottle`, `celery`, `falcon`, `flask`, `litestar`, `quart`, `sanic`,
`starlette`, and `typer`. Unknown names are still rejected, so that a typo does not pass silently.
The default stays `["python", "fastapi", "dishka"]`.

## Consequences

- Configurations that list any of the new names load; nothing else about analysis changes, and
  the configuration digest of existing configurations is unchanged.
- `tests/test_config.py` checks that every framework with an application constructor, and
  `django`, can be listed.
- If a future capability needs to be selected per world, it must be one whose absence cannot hide
  code that may run, and that decision needs its own record.
