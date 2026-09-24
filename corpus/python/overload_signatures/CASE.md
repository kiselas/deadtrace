# Overload signatures

`parse` and `Reader.read` each have two `@overload` signatures before their
implementation, as in `rich.progress.open`. The implementation replaces the name, but
`typing` keeps every signature for `typing.get_overloads`, and type checkers read them;
they live and die with the implementation. `main` calls both implementations, so reporting
a signature as unreached is unsafe. `unused` has overload signatures and an implementation
that nothing calls, so all of them must stay candidates.

Recorded as a known violation of the analysis contract (ADR-0006) and met from model
revision `python-fastapi-dishka/9` (ADR-0012).
