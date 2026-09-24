# 50k-line scale fixture: baseline before optimization

Measured 2026-09-21 with `deadtrace 0.1.0a0`, model revision `python-fastapi-dishka/4`, LibCST
1.9.0, on Windows 11 AMD64, CPython 3.12.14 (uv-managed build).

Fixture: `uv run python benchmarks/generate_scale_fixture.py .benchmark-work/scale-50k --lines
50000` (251 files, 50,251 lines, 753,742 characters). Three fresh-process runs of
`uv run deadtrace benchmark .benchmark-work/scale-50k --runs 1 --format json`, nothing else
loading the machine. Raw artifacts: `2026-09-21-scale-50k-run1.json`,
`2026-09-21-scale-50k-run2.json`, `2026-09-21-scale-50k-run3.json`.

This is a synthetic fixture and a performance guard only. It says nothing about precision or
field quality.

## Wall time (seconds, three runs)

| Stage | min | median | max |
| --- | --- | --- | --- |
| `collect_seconds` | 7.218 | 7.608 | 8.373 |
| `frontend_seconds` | 17.748 | 18.044 | 18.139 |
| `solve_seconds` | 0.002 | 0.002 | 0.003 |
| `report_seconds` | 0.017 | 0.017 | 0.029 |
| `total_seconds` | 24.968 | 25.654 | 26.514 |

Budget: total below 30 seconds — **met** at the median. Process peak RSS: 110,960,640 / 112,107,520
/ 111,632,384 bytes across the three runs (budget 1 GiB, met).

For scale, the included FastAPI/Dishka reference project scans in a median 0.067 seconds over five
runs.

## Sub-stages (median of three runs)

| Sub-stage | seconds | share of total |
| --- | --- | --- |
| `frontend.symbols` | 6.535 | 25.5% |
| `frontend.frameworks_discover` | 6.185 | 24.1% |
| `collect.inventory_visit` | 6.181 | 24.1% |
| `frontend.imports` | 2.912 | 11.3% |
| `frontend.symbol_flow` | 1.541 | 6.0% |
| `collect.inventory_parse` | 1.286 | 5.0% |
| `frontend.parse` | 1.108 | 4.3% |
| `collect.read` | 0.048 | 0.2% |
| `collect.discover` | 0.042 | 0.2% |
| `collect.verify_discover` | 0.040 | 0.2% |
| `collect.verify_read` | 0.032 | 0.1% |
| `report.render` | 0.017 | 0.1% |
| `solve.findings` | 0.002 | 0.0% |
| `frontend.declaration_flow` | 0.001 | 0.0% |
| `frontend.target_environment` | 0.001 | 0.0% |
| `frontend.entry_points` | 0.000 | 0.0% |
| `solve.reachability` | 0.000 | 0.0% |
| `frontend.graph` | 0.000 | 0.0% |
| `frontend.frameworks_plans` | 0.000 | 0.0% |
| `frontend.class_fields` | 0.000 | 0.0% |
| `frontend.pytest` | 0.000 | 0.0% |
| `frontend.frameworks_graph` | 0.000 | 0.0% |

## Counters

| Counter | Value |
| --- | --- |
| `collect.attempts` | 1 |
| `collect.characters` | 753,742 |
| `collect.files_read` | 251 |
| `collect.read_errors` | 0 |
| `edges` | 0 |
| `files` | 251 |
| `findings` | 250 |
| `frameworks.edges` | 0 |
| `frameworks.requirements` | 1 |
| `frontend.boundaries` | 0 |
| `frontend.edges` | 0 |
| `frontend.import_bindings` | 1 |
| `frontend.modules` | 251 |
| `frontend.parse_failures` | 0 |
| `frontend.symbols` | 251 |
| `graph.boundaries` | 0 |
| `graph.requirements` | 1 |
| `lines` | 50,251 |
| `nodes` | 502 |
| `worlds` | 1 |

## Where the time goes

- **LibCST metadata resolution: 21.813 s (85.0%).** Four sub-stages — `collect.inventory_visit`,
  `frontend.symbols`, `frontend.imports`, and
  `frontend.frameworks_discover` — each construct a `MetadataWrapper` per module and resolve
  `PositionProvider`, which LibCST implements by regenerating the module's source. The five
  construction sites are `inventory_source`, the symbol pass in `build_python_program`,
  `_collect_imports`, `_top_level_assignments`, and `_top_level_calls`; the first two also
  deep-copy the tree because they do not pass `unsafe_skip_copy=True`. cProfile counts 1,255
  `resolve_many` calls for 251 modules, five per module.
- **Parsing: 2.393 s (9.3%).** Every module is parsed twice, once by the
  inventory and once by the frontend.
- **Flow extraction: 1.541 s (6.0%).**
- **File discovery, reading, hashing, and snapshot verification: 0.161 s (0.6%).**
- **Reachability and findings: 0.002 s (0.0%).**
- **JSON report rendering: 0.017 s**, measured separately.

## Implications for the roadmap

- PERF-02 assumes collection time is spent in path resolution, directory walks, snapshot
  verification, decoding, and hashing. Measured, those cost 0.161 s. The `collect` stage
  (7.608 s) is dominated by the inventory's own LibCST parse
  and metadata pass. Its acceptance criterion should be re-stated before any work starts.
- PERF-03 has one lever worth more than everything else combined: build one
  `MetadataWrapper` per module with `unsafe_skip_copy=True`, resolve `PositionProvider` once,
  and share the positions across inventory, frontend, and framework discovery. The ceiling is
  the 85.0% above; parsing once instead of twice is the next 9.3%.
- The solver is not a factor at this scale.

## Profile excerpt

cProfile in a separate fresh process via `benchmarks/profile_scan.py`; profiler overhead
roughly doubles wall time, so only the ratios matter. Path prefixes are sanitized.

### By cumulative time

```text
212830608 function calls (192686749 primitive calls) in 77.693 seconds

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
        1    0.000    0.000   82.692   82.692 src/deadtrace/analysis.py:66(analyze)
2510/1255    0.004    0.000   52.694    0.042 site-packages/libcst/metadata/wrapper.py:183(resolve_many)
2510/1255    0.031    0.000   52.691    0.042 site-packages/libcst/metadata/wrapper.py:69(_resolve_impl)
4004756/2012    4.902    0.000   41.793    0.021 site-packages/libcst/_nodes/base.py:211(visit)
3766/2009    0.092    0.000   41.740    0.021 site-packages/libcst/_nodes/internal.py:217(visit_body_sequence)
403490/53525    0.447    0.000   41.727    0.001 site-packages/libcst/_nodes/internal.py:180(visit_body_iterable)
     2009    0.006    0.000   41.344    0.021 site-packages/libcst/_nodes/statement.py:700(_visit_and_replace_children)
3195465/216433    3.137    0.000   40.371    0.000 site-packages/libcst/_nodes/internal.py:73(visit_required)
   397969    0.507    0.000   38.792    0.000 site-packages/libcst/_nodes/statement.py:437(_visit_and_replace_children)
        1    0.063    0.063   37.908   37.908 src/deadtrace/python_frontend.py:104(build_python_program)
     1757    0.004    0.000   36.346    0.021 site-packages/libcst/_nodes/module.py:82(visit)
     1757    0.007    0.000   36.327    0.021 site-packages/libcst/_nodes/module.py:71(_visit_and_replace_children)
     1757    0.017    0.000   36.258    0.021 site-packages/libcst/_nodes/statement.py:1996(_visit_and_replace_children)
      753    0.003    0.000   33.073    0.044 site-packages/libcst/metadata/wrapper.py:170(resolve)
      502    0.003    0.000   31.028    0.062 site-packages/libcst/metadata/wrapper.py:198(visit)
2409032/819040    1.209    0.000   27.854    0.000 site-packages/libcst/_nodes/internal.py:167(visit_sequence)
     1255    0.043    0.000   27.661    0.022 site-packages/libcst/metadata/base_provider.py:85(_gen)
     1255    0.005    0.000   27.603    0.022 site-packages/libcst/metadata/position_provider.py:131(_gen_impl)
2505010/1255    2.232    0.000   27.597    0.022 site-packages/libcst/_nodes/base.py:298(_codegen)
     1255    0.003    0.000   27.586    0.022 site-packages/libcst/_nodes/module.py:95(_codegen_impl)
     1255    0.011    0.000   27.575    0.022 site-packages/libcst/_nodes/statement.py:2035(_codegen_impl)
2809047/1217032    1.438    0.000   27.376    0.000 site-packages/libcst/_nodes/internal.py:147(visit_iterable)
     1255    0.071    0.000   27.326    0.022 site-packages/libcst/_nodes/statement.py:708(_codegen_impl)
   248730    0.166    0.000   26.510    0.000 site-packages/libcst/_nodes/statement.py:455(_codegen_impl)
```

### By internal time

```text
212830608 function calls (192686749 primitive calls) in 77.693 seconds

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
22068116/22068072    4.974    0.000    8.904    0.000 {built-in method builtins.isinstance}
4004756/2012    4.902    0.000   41.793    0.021 site-packages/libcst/_nodes/base.py:211(visit)
3195465/216433    3.137    0.000   40.371    0.000 site-packages/libcst/_nodes/internal.py:73(visit_required)
1002004/502    2.722    0.000    9.136    0.018 site-packages/libcst/_nodes/base.py:327(deep_clone)
  2505010    2.335    0.000    5.637    0.000 site-packages/libcst/metadata/position_provider.py:62(after_codegen)
  1747963    2.283    0.000    2.505    0.000 stdlib/contextlib.py:104(__init__)
2505010/1255    2.232    0.000   27.597    0.022 site-packages/libcst/_nodes/base.py:298(_codegen)
  2505010    2.176    0.000    2.869    0.000 site-packages/libcst/_position.py:48(__init__)
 12883836    2.126    0.000    2.126    0.000 {built-in method builtins.getattr}
 12027892    1.970    0.000    3.929    0.000 <frozen abc>:117(__instancecheck__)
 12027892    1.959    0.000    1.959    0.000 {built-in method _abc._abc_instancecheck}
 14664594    1.936    0.000    1.936    0.000 {method 'get' of 'dict' objects}
      502    1.825    0.004    3.552    0.007 site-packages/libcst/_parser/entrypoints.py:25(_parse)
  2494920    1.779    0.000    4.603    0.000 site-packages/libcst/metadata/position_provider.py:94(record_syntactic_position)
  4018835    1.626    0.000    2.167    0.000 site-packages/libcst/_batched_visitor.py:148(on_visit_attribute)
  4018835    1.604    0.000    2.130    0.000 site-packages/libcst/_batched_visitor.py:157(on_leave_attribute)
```
