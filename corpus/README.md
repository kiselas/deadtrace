# Deadtrace corpus

This corpus contains source projects analyzed as data. Deadtrace's static scanner must never import
or execute them. A separate, explicitly trusted `tests/oracle/` suite imports selected reference
applications to confirm framework behavior against pinned development dependencies.

Each case has independent expectations in `CASE.md` and `CASE.toml`: exact worlds, finding and
limitation codes, plus target reachability where applicable. Analyzer output is not the oracle.
Private pilot source must not be copied here without permission; regressions derived from a pilot
are minimized and rewritten.

Current tracks:

- `reference/fastapi_dishka_basic`: executable FastAPI 0.141.1 + Dishka 1.10.1 vertical slice.
- `frameworks/`: isolated FastAPI, Dishka, Pydantic, pytest, safety, and limitation patterns.
- `python/`: language-level flow, implicit-hook, and conservative-boundary patterns.

Run `deadtrace cases validate corpus` to execute the semantic manifests without importing target
modules. The trusted runtime oracle remains a separate pytest marker and environment.
