# 0.1.0a2 support matrix

| Area | Alpha scope | Evidence / limit |
| --- | --- | --- |
| Runtime | CPython 3.12, 3.13 and 3.14 | Package requires >=3.12,<3.15; CI runs tests and the wheel smoke on each, on Linux and Windows. Corpus reports are byte-identical between versions. 0.1.0a1 supported 3.12 only |
| Python | Static references, imports, inheritance, receiver joins, bounded dispatch and API closure | Model 35; corpus and unit tests; general dynamic Python is conservative |
| FastAPI | Modeled apps/routers, Depends, lifespan, background tasks, bounded factories | Supported >=0.100,<1; oracle pins 0.141.1 |
| Dishka | Modeled providers, aliases, context, injections, route/container/lifecycle patterns | Supported >=1.0,<2; oracle pins 1.10.1; components/conditional activation guarded |
| pytest | Separate test worlds, fixture/hook/plugin/configuration discovery | Repository tests and corpus; arbitrary dynamic plugins guarded |
| Other frameworks | Bounded static roots/hooks listed in README | Corpus examples are pattern coverage, not complete framework support |
| Outputs | Inventory schema 0; semantic schema 1; explanations/baselines/comparison | Alpha compatibility; model/support differences affect comparability |
| Public installation | Wheel + sdist; runtime packaging, Rich and Typer only | Same CI-built wheel tested on both release operating systems |

The pinned HTTPX 0.28.1 belongs to the trusted oracle environment, not scanner runtime. Other exact
FastAPI/Dishka versions within supported ranges emit DT4002; incompatible versions emit DT4001 and
block strong negative findings. An unpinned version is not presented as verified.

Unknown values, dynamic reflection/imports, descriptors/metaclasses and arbitrary external
consumers can protect large regions, reducing recall. The independent object_setattr_store recall
gap is retained under fixtures/recall-gaps on this release. On two blind samples of public GitHub projects, 97 of 195 reviewed findings were true at model
33 (49.7%) and 76 of 194 at model 35 (39.2%); see [the cohort document](field/2026-10-cohort.md)
for the verdicts and the false-finding classes. Model-31 development-sample injection recall was 474/721, including Pydantic 0/76: [measurement](public-return-api-results-2026-10-05.md)
and [reviewed diagnosis](pydantic-recall-review-2026-10-05.md). These are sample-specific research
results, not a general precision/recall guarantee. macOS and Python 3.15+ are not
release-verified. See [analysis contract](analysis-contract.md).
