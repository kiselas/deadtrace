# Hooks called by external base classes

`ast.NodeVisitor.visit` calls `visit_Call` on `CallCounter`, `threading.Thread.start` runs
`Worker.run`, and a `logging.Handler` subclass has `emit` called for every record. Deadtrace does not
read those libraries, so it cannot know which method names they call; each such method may run once
its class is used. Reporting any of them as unreached is unsafe. `unused_control` is referenced
nowhere and must stay a candidate.

Recorded as a known violation of the analysis contract (ADR-0006) and met from model
revision `python-fastapi-dishka/6` (ADR-0009).
