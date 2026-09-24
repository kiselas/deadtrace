# Nested function bound in one branch

`main` binds `write` with a nested `def` when compression is on and assigns `print` to it
otherwise, then calls `write`, as `RawTokenFormatter.format` in pygments does. Either
binding may be the one that runs, so reporting the nested `main.write` as unreached is
unsafe. `main.unused` is a nested function that nothing calls and must stay a candidate.

Recorded as a known violation of the analysis contract (ADR-0006) and met from model
revision `python-fastapi-dishka/9` (ADR-0012).
