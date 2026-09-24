# IPython display hooks

`Table` defines `_repr_html_` and `_repr_mimebundle_`, as `rich.jupyter` does. IPython and
Jupyter call these single-underscore hooks by name on any object they display, and `main`
returns a `Table`, so reporting either hook as unreached is unsafe. The single-underscore
name `_render` is an ordinary private method that nothing calls and must stay a candidate.

Recorded as a known violation of the analysis contract (ADR-0006) and met from model
revision `python-fastapi-dishka/9` (ADR-0012).
