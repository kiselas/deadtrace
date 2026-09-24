# Command registered by an unmodeled CLI framework

`cli` is registered with `@click.command()`. Click, which Deadtrace does not model, runs it when the
console script is invoked; no Python code in the project calls it. Reporting it as unreached is
unsafe. A guard local to the decorated function and a weakened world are both acceptable outcomes,
so this case has no control candidate.

Recorded as a known violation of the analysis contract (ADR-0006) and met from model
revision `python-fastapi-dishka/5` (ADR-0008).
