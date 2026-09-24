# 50k-line scale fixture: one parse and one position pass per module (PERF-03)

Measured 2026-09-24 on the same host and fixture as
[the 2026-09-21 baseline](2026-09-21-scale-50k-baseline.md): Windows 11 AMD64, CPython 3.12.14
(uv-managed), LibCST 1.9.0, `generate_scale_fixture.py --lines 50000` (251 files, 50,251 lines).

The host was noticeably noisier than on 2026-09-21, so the numbers below are **not** compared with
the earlier baseline. Instead `main` (`a7ec1a3`) and this change were benchmarked in the same session,
alternating fresh processes: main, branch, main, branch, main, branch. Raw artifacts:
`2026-09-24-scale-50k-main-run{1,2,3}.json` and `2026-09-24-scale-50k-single-parse-run{1,2,3}.json`.
The `main` artifacts use benchmark schema 2 and the branch artifacts schema 3; the only difference is
the sub-stage key set described in ADR-0004.

## Wall time (seconds)

| | runs | median |
| --- | --- | --- |
| `main` total | 31.560 / 45.670 / 36.005 | **36.005** |
| single parse total | 10.723 / 13.242 / 17.397 | **13.242** |

Median speed-up ×2.7. Process peak RSS 111,083,520 bytes on `main`, 165,773,312 bytes with the
change: every module's parse and position map now coexist until the frontend has used them. Both are
far below the 1 GiB budget.

## Sub-stages (median seconds)

| Sub-stage | `main` | single parse |
| --- | --- | --- |
| `collect.inventory_parse` → `collect.parse` (now includes the single position pass) | 1.661 | 7.370 |
| `collect.inventory_visit` | 7.994 | 1.830 |
| `frontend.parse` | 1.414 | 0.000 |
| `frontend.symbols` | 7.793 | 2.039 |
| `frontend.imports` | 3.465 | 0.000 |
| `frontend.frameworks_discover` | 12.435 | 0.001 |
| `frontend.symbol_flow` (unchanged code) | 3.157 | 1.684 |

`frontend.symbol_flow` runs identical code in both columns; its spread shows how much of the
difference between single runs is host noise. The medians still separate by a wide margin.

## What remains

- `collect.parse` is now the largest stage: roughly a third LibCST parsing and two thirds the one
  `PositionProvider` pass, which regenerates the module source.
- `collect.inventory_visit` and `frontend.symbols` walk the full tree twice for the same
  `FunctionDef`/`ClassDef` nodes. Merging them into one visitor is the next measurable lever.
- The solver remains negligible.

This is a synthetic fixture and a performance guard only.
