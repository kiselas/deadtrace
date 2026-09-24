# Standard-library `ast` frontend (ADR-0007)

Measured 2026-09-24 on the host of the earlier results: Windows 11 AMD64, CPython 3.12.14
(uv-managed), model revision `python-fastapi-dishka/4`. `main` ran with LibCST 1.9.0 from a
`git worktree` of `d14e77c` on `PYTHONPATH`; the change ran from the working tree. Runs alternated in
fresh processes: main, change, main, change. The host was less loaded than during the PERF-03b
measurements. Main artifacts are benchmark schema 3 and the change's schema 4; the only difference is
`descriptor.libcst_version` becoming `descriptor.parser` (`ast/3.12`). Raw artifacts:
`2026-09-24-stdlib-ast/<target>-<main|branch>-run<N>.json`.

Inputs are those of `2026-09-24-indexed-lookups.md`: the scale fixture and the 20k and 50k service
fixtures from the committed generators, and rich 15.0.0, `_pytest` 9.1.1, pydantic 2.13.5, libcst
1.9.0, and mypy 2.3.1 staged from the locked environment before LibCST left it. pygments 2.21.0
replaces libcst in the staging defaults and was measured with the change only.

## Wall time and memory

| Target | lines | runs | `main` median, s | change median, s | factor | peak RSS, MiB |
| --- | --- | --- | --- | --- | --- | --- |
| scale fixture | 50,251 | 3 | 11.75 | 0.61 | 19× | 159 → 84 |
| service fixture | 50,226 | 3 | 16.31 | 1.23 | 13× | 237 → 141 |
| service fixture | 20,334 | 1 | 8.87 | 0.40 | 22× | 120 → 77 |
| mypy | 128,969 | 3 | 65.78 | 2.58 | 25× | 573 → 256 |
| libcst | 103,335 | 1 | 40.67 | 1.59 | 26× | 548 → 171 |
| pydantic | 45,867 | 1 | 16.67 | 0.70 | 24× | 192 → 95 |
| `_pytest` | 37,830 | 1 | 14.86 | 0.56 | 27× | 169 → 87 |
| rich | 38,615 | 1 | 14.79 | 0.49 | 30× | 191 → 82 |
| pygments | 128,552 | 2 | — | 1.29 | — | 168 |

All runs: main 11.67–22.79 s on the 50k inputs, the change 0.60–1.28 s. The first pygments run took
6.31 s, of which `collect.read` was 4.56 s: its files had just been copied, and the operating system's
first read of new files dominated. The second run read them in 0.08 s. Every other input had been read
before.

## Where the time went (medians, seconds)

| Target | parse and positions | inventory walk | symbols | flow |
| --- | --- | --- | --- | --- |
| mypy, `main` | 29.87 | 9.87 | 10.64 | 12.63 |
| mypy, change | 0.92 | 0.07 | 0.30 | 0.94 |
| service 50k, `main` | 8.03 | 2.57 | 2.95 | 1.90 |
| service 50k, change | 0.22 | 0.13 | 0.08 | 0.23 |

## Equivalence

- Semantic and `--inventory-only` reports and exit codes for the 36 targets of the PERF-03b
  comparison: 144 of 144 files byte-identical.
- Canonical fact dumps of 51 targets, including the five installed packages with configured worlds
  and Deadtrace's own previous source: identical under a fixed `PYTHONHASHSEED`; without one, only
  the set-ordered `WorldPlan.root_provenance` differs, as it does between two runs of the same code.
- The ADR-0006 known-violation pins are unchanged.

## What the numbers say about the budget

- Both 50k fixtures finish in 0.6–1.3 seconds, far inside 30 seconds, and 129k lines of mypy in
  2.6 seconds.
- Memory is about 2 MiB per 1,000 lines on the installed packages (256 MiB for mypy), so 1 GiB is
  reached near 450,000–500,000 lines. Syntax trees are still retained until the frontend finishes;
  releasing each after extracting its facts is the next memory lever.
- Parsing and flow extraction now take similar shares; the solver and framework stages remain small.

This is performance evidence only; none of these inputs says anything about precision.
