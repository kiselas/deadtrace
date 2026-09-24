# Python-core soundness rules (ADR-0008, model revision 5)

Measured 2026-09-24 on the host of the earlier results: Windows 11 AMD64, CPython 3.12.14. `main`
(`bea764b`, model revision 4) ran from a `git worktree` on `PYTHONPATH`; the change ran from the
working tree. Runs alternated in fresh processes. The host was loaded by unrelated work during the
session — `main` took 1.22 seconds on the scale fixture against 0.61 seconds in the unloaded
FRONTEND-02 runs — so the ratios are more reliable than the absolute times. Raw artifacts:
`2026-09-24-python-core-soundness/<target>-<main|branch>-run<N>.json`.

## Cost

| Target | runs | `main` median, s | change median, s | change | edges | boundaries |
| --- | --- | --- | --- | --- | --- | --- |
| scale fixture, 50k lines | 3 | 1.22 | 1.34 | +10% | 0 → 0 | 0 → 0 |
| service fixture, 50k lines | 3 | 2.09 | 2.78 | +33% | 19,759 → 29,015 | 0 → 0 |
| mypy, 129k lines | 3 | 4.43 | 5.04 | +14% | 17,921 → 35,601 | 3,069 → 6,254 |
| pygments, 128k lines | 1 | 1.58 | 1.79 | +13% | 3,469 → 5,900 | 112 → 384 |
| rich, 39k lines | 1 | 0.53 | 0.62 | +17% | 1,576 → 2,897 | 128 → 641 |

Peak RSS changes by at most 10 MiB (mypy: 255 → 265 MiB). The extra time is in flow extraction,
which now looks at every name and attribute rather than only at calls, and in resolving class
hierarchies. The new edges are the `member`, `inherit`, and `annotation` edges and the dispatch and
decorator edges; the new boundaries are one `escaped_reference` and one `unresolved_method_dispatch`
boundary per scope that needs them, and one `decorator_registration` boundary per function under an
unmodeled decorator.

## What it buys

- The thirteen known-violation cases meet their expectations, each with its control candidate still
  reported.
- The audit probes: a FastAPI project from ten findings, seven of them false, to two true ones; a
  plain script from six findings, five false, to one true one.
- The 50k service fixture still reports exactly its 178 unused functions, so the framework-shaped
  code lost no findings.

This is performance evidence only; the precision statements rest on the corpus and the probes.
