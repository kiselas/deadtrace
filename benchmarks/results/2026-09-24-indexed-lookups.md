# Service fixture and installed sources: indexed lookups (PERF-00, PERF-03b)

Measured 2026-09-24 on the host of the earlier results: Windows 11 AMD64, CPython 3.12.14
(uv-managed), LibCST 1.9.0, model revision `python-fastapi-dishka/4`.

Inputs:

- `generate_service_fixture.py --lines 50000`: 182 files, 50,226 lines, 9,440 nodes, 19,759 edges,
  178 findings in one complete world. The same generator with `--lines 20000`: 76 files, 20,334
  lines.
- `stage_installed_sources.py`: rich 15.0.0, pytest 9.1.1 (`_pytest`), pydantic 2.13.5, libcst
  1.9.0, and mypy 2.3.1 from the locked environment, 38k to 129k lines each. They have no
  configured roots, so their worlds are invalid and they yield no findings.

`main` (`1c4962d`) and the change were run as alternating fresh processes in one session: main,
branch, main, branch. The host was loaded by unrelated processes during the session (about 57% CPU
before the last pairs), so total times vary between pairs by up to a third. `collect.parse` runs
unchanged code in both columns; its spread shows the noise. The stages the change touches are the
reliable signal. Raw artifacts: `2026-09-24-indexed-lookups/<target>-<main|branch>-run<N>.json`.

## Stages the change touches (median seconds)

`frameworks_discover`, `frameworks_plans`, `symbol_flow`, and `solve.findings`:

| Target | runs | `main` | change | factor |
| --- | --- | --- | --- | --- |
| service fixture, 50k lines | 3 | 8.58 / 2.40 / 2.76 / 2.18 | 0.33 / 0.02 / 1.87 / 0.02 | 7.1× |
| service fixture, 20k lines | 1 | 1.61 / 0.32 / 1.21 / 0.29 | 0.41 / 0.01 / 1.24 / 0.01 | 2.0× |
| mypy, 129k lines | 3 | 1.49 / 0.00 / 30.04 / 0.00 | 0.02 / 0.00 / 17.23 / 0.00 | 1.8× |
| libcst, 103k lines | 1 | 2.33 / 0.00 / 11.15 / 0.00 | 0.03 / 0.00 / 8.15 / 0.00 | 1.6× |
| pydantic, 46k lines | 1 | 0.30 / 0.00 / 6.04 / 0.00 | 0.01 / 0.00 / 2.73 / 0.00 | 2.3× |
| `_pytest`, 38k lines | 1 | 0.21 / 0.00 / 4.85 / 0.00 | 0.01 / 0.00 / 3.75 / 0.00 | 1.3× |
| rich, 39k lines | 1 | 0.11 / 0.00 / 2.71 / 0.00 | 0.01 / 0.00 / 1.61 / 0.00 | 1.7× |

On `main`, going from the 20k to the 50k service fixture (2.5 times the lines) multiplied framework
discovery by 5.3 and planning and finding construction by 7.5: quadratic growth. With the change the
same stages stay below half a second at both sizes.

## Total wall time and memory

| Target | `main` runs, s | change runs, s |
| --- | --- | --- |
| service fixture, 50k lines | 30.14 / 33.83 / 38.13 | 23.42 / 23.04 / 17.59 |
| mypy | 72.74 / 98.38 / 96.36 | 54.23 / 84.92 / 83.97 |
| libcst | 64.66 | 56.46 |

Three more runs of the change on the 50k service fixture while nothing else loaded the host took
15.39, 15.82, and 17.29 seconds (`service-50k-branch-unloaded-run<N>.json`). No unloaded `main`
runs were kept. Process peak RSS is unchanged: 236–239 MiB on the service fixture, 549–571 MiB
on libcst and mypy.

## Report equivalence

Semantic and `--inventory-only` JSON reports and exit codes were captured with `main` and with the
change for all 18 corpus cases, the 6 seed cases, the 50k scale fixture, the 50k service fixture,
three more generated FastAPI/Dishka applications, two small probe projects, and the five
installed-source projects: 144 of 144 files are byte-identical.

## What the numbers say about the budget

- The scale fixture alone is not evidence for the 30-second budget: it has no edges or framework
  objects. On the 50k service fixture `main` takes 30–38 seconds under load, at or over the
  budget. The change brings the same input to 17–23 seconds under load and 15–17 seconds unloaded.
- Memory grows with parsed trees and position maps: 555–571 MiB for mypy's 129k lines, about
  4.3 MiB per 1,000 lines. At that rate the 1 GiB budget is exceeded near 240,000 lines. This
  change does not address memory.
- What remains is the work on LibCST trees: `collect.parse` (the single parse and position pass),
  the inventory and symbol visitors, and the flow visitors, whose every `visit` rebuilds the
  visited nodes. With the change those stages take 99% of the mypy scan.

This is performance evidence only; none of these inputs says anything about precision.
