# 0.1.0a6 support matrix

| Area | Alpha scope | Evidence / limit |
| --- | --- | --- |
| Runtime | CPython 3.12, 3.13 and 3.14 | Package requires >=3.12,<3.15; CI runs tests and the wheel smoke on each, on Linux and Windows. Corpus reports are byte-identical between versions. 0.1.0a1 supported 3.12 only |
| Python | Static references, imports, inheritance, receiver joins, bounded dispatch and API closure | Model 88; corpus and unit tests; general dynamic Python is conservative |
| FastAPI | Modeled apps/routers, Depends, lifespan, background tasks, bounded factories | Supported >=0.100,<1; oracle pins 0.141.1 |
| Dishka | Modeled providers, aliases, context, injections, route/container/lifecycle patterns | Supported >=1.0,<2; oracle pins 1.10.1; components/conditional activation guarded |
| pytest | Separate test worlds, fixture/hook/plugin/configuration discovery | Repository tests and corpus; arbitrary dynamic plugins guarded |
| Other frameworks | Bounded static roots/hooks listed in README | Corpus examples are pattern coverage, not complete framework support |
| Outputs | Inventory schema 0; semantic schema 1 (with `blocked_findings`, ADR-0071); explanations/baselines/comparison | Alpha compatibility; model/support differences affect comparability |
| Public installation | Wheel + sdist; runtime packaging, Rich and Typer only | Same CI-built wheel tested on both release operating systems |

Unreleased model 94 also models local Cookiecutter extension objects explicitly named
in `cookiecutter.json`, including static package reexports. Resolution is relative to
that manifest's directory; external extensions and dynamically rendered names remain
outside this rule. Its independent case and paired evaluation on 531 reviewed development
projects removed one false finding with no new findings or lost reviewed true findings;
exact seed-7 injection outcomes were unchanged. This is development evidence, not a new
blind precision estimate: [method and results](field/2026-10-cohort.md).

The pinned HTTPX 0.28.1 belongs to the trusted oracle environment, not scanner runtime. Other exact
FastAPI/Dishka versions within supported ranges emit DT4002; incompatible versions emit DT4001 and
block strong negative findings. An unpinned version is not presented as verified.

Unknown values, dynamic reflection/imports, descriptors/metaclasses and arbitrary external
consumers can protect large regions, reducing recall. The independent object_setattr_store recall
gap is retained under fixtures/recall-gaps on this release. On four blind samples of public GitHub projects, 104 of 159 reviewed findings were true at model 53
(65.4%, 95% CI 57.7-72.4), 87 of 129 at model 59 (67.4%, 59.0-74.9), 100 of 140 at model 75
(71.4%, 63.5-78.3), and 124 of 169 at model 88 (73.4%, 66.2-79.5; `RCH001` and `RCH004` 80.0%,
`RCH002` 0 of 14); earlier blind samples were 39-50% at models 33 and 35. Vulture 2.16 on 224
public projects was 15.8% under the same review; see [the cohort document](field/2026-10-cohort.md)
for the verdicts and the false-finding classes. Injection recall at models 75 and 88 is 534/721 on the development packages (74.1%; 592 found, 58 of
them blocked) and 964/1,565 on 39 held-out packages (61.6%); Pydantic stays at 0/76, because it
imports modules by names from data. Model-31 recall was 474/721: [measurement](public-return-api-results-2026-10-05.md)
and [reviewed diagnosis](pydantic-recall-review-2026-10-05.md). These are sample-specific research
results, not a general precision/recall guarantee. macOS and Python 3.15+ are not
release-verified. See [analysis contract](analysis-contract.md).
