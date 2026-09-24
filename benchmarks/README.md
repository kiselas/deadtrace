# Scale benchmark protocol

Generate a deterministic synthetic project outside the repository, then run a cold single-pass
benchmark from a fresh process:

```console
uv run python benchmarks/generate_scale_fixture.py .benchmark-work/scale-50k --lines 50000
uv run deadtrace benchmark .benchmark-work/scale-50k --runs 1 \
  --format json --output dist/scale-50k-benchmark.json
```

The preliminary alpha budget from the roadmap is 50,000 Python lines, total cold scan below 30
seconds, and process peak RSS below 1 GiB on a recorded host. The benchmark is a performance guard,
not field-quality or precision evidence. Run it with nothing else loading the machine; a concurrent
test run visibly inflates the numbers.

## Three fixtures, three different costs

The scale fixture holds one function per module and yields no edges, classes, imports, or framework
objects. It measures parsing and per-module passes only, so it cannot show costs that grow with the
number of symbols, calls, routes, or bindings. Two more inputs cover that:

```console
uv run python benchmarks/generate_service_fixture.py .benchmark-work/service-50k --lines 50000
uv run deadtrace benchmark .benchmark-work/service-50k --runs 1 \
  --format json --output dist/service-50k-benchmark.json

uv run python benchmarks/stage_installed_sources.py .benchmark-work/real
uv run deadtrace benchmark .benchmark-work/real/mypy --runs 1 \
  --format json --output dist/real-mypy-benchmark.json
```

- **Service fixture.** A repeated FastAPI/Dishka/Pydantic domain package: models with validators,
  a repository and a service class, helpers, a shared utility module, a provider, and a
  `DishkaRoute` router whose endpoints use `FromDishka` and `Depends`. Every domain carries one
  unused function, so the scan runs in a complete world with findings. The budget applies to the
  50,000-line service fixture as well as to the scale fixture.
- **Installed third-party sources.** `stage_installed_sources.py` copies the `.py` files of rich,
  `_pytest`, pydantic, pygments, and mypy from the locked development environment as bytes, without
  importing them; the versions are fixed by `uv.lock` and printed by the script. Without
  configured worlds they get automatic library and scripts worlds (ADR-0011), except `_pytest`,
  whose modules are all private; they measure the whole analysis on real code, including code
  much larger than 50,000 lines.

Neither input is precision evidence.

## CI guard

The `Performance` workflow (`.github/workflows/performance.yml`) runs on demand from the
Actions tab, on Linux and Windows. It builds the wheel, generates both fixtures under the
runner's temporary directory, never in the repository, benchmarks them from the installed
wheel, uploads the JSON artifacts, and fails when `benchmarks/check_budget.py` finds a median
total of 30 seconds or more, or a peak RSS of 1 GiB or more:

```console
uv run python benchmarks/check_budget.py dist/scale-50k-benchmark.json \
  dist/service-50k-benchmark.json --max-seconds 30 --max-rss-mib 1024
```

It stays manual until the variance of hosted runners is measured; then it can run on a
schedule or become required, with thresholds agreed from those measurements.

## What the artifact contains

`deadtrace benchmark` writes a schema-4 JSON artifact:

- `descriptor` — source, configuration, and model digests, the Deadtrace version, and the parser
  (`ast/<major>.<minor>` of the interpreter). Identical inputs on identical software produce an
  identical descriptor.
- `counters` — deterministic sizes: files, lines, nodes, edges, worlds, and the sub-stage counters
  from `deadtrace.timing.COUNTERS` (files read, characters, parse failures, symbols, import
  bindings, edges, boundaries, requirements, findings). Runs of the same input must agree; the
  benchmark stops when they do not.
- `samples` — one entry per run with `collect_seconds`, `frontend_seconds`, `solve_seconds`,
  `report_seconds`, `total_seconds`, and `stages`, the sub-stage seconds named in
  `deadtrace.timing.STAGES`. Sub-stages are nested inside their parent stage and never exceed it.
  `total_seconds` covers the analysis; `report_seconds` measures JSON report rendering separately.
- `summary` — min, median, and max per stage and per sub-stage.
- `host` — operating system, release, machine, and Python implementation and version. No host name.
- `process_peak_rss_bytes` — the OS-reported process lifetime peak. Timed runs never enable
  `tracemalloc`; its instrumentation overhead would invalidate the budget.
- `volatile_fields` — the fields that may differ between runs or hosts. Every other field is
  deterministic and can be compared byte for byte.

The artifact never contains paths, source text, symbol names, configuration values, user names, or
host names.

## Profiling before optimizing

A CPU profile is taken in a separate fresh process and is never mixed into timed runs:

```console
uv run python -m cProfile -o profile.prof benchmarks/profile_scan.py .benchmark-work/scale-50k
```

Strip user-specific path prefixes before committing any profile excerpt. Evidence that backs a
roadmap status change lives under `benchmarks/results/`: the raw JSON artifacts plus a short
markdown summary naming the fixture generator arguments and what the numbers mean.

The generated project deliberately contains no private or third-party source and must not be added
to the semantic corpus. Delete `.benchmark-work/` after inspection; it is ignored by Git.
