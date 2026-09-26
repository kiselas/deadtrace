# Calls in annotations

`Annotated` metadata builds objects whose callables a framework calls later:
`typer.Option(callback=show_version)` in a parameter annotation, and `AfterValidator(normalize)`
in a Pydantic field annotation. Python evaluates a parameter annotation when the `def` runs and a
class-body annotation when the class body runs; under `from __future__ import annotations`, Typer
and Pydantic evaluate them when they read the signature or build the model. Either way the
callables may run.

The unsafe outcome is reporting `show_version` or `normalize` as unreached because annotations
were treated as inert text. A helper that nothing references is still reported.
