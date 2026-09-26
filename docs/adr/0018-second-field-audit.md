# ADR-0018: Second field audit: exclusions, version ranges, and CLI commands (model revision 12)

**Status:** Accepted, 2026-09-26.

## Context

A second pass over the projects of ADR-0017, and over five more local checkouts, among them a
monorepo of twelve FastAPI services with 624k lines, found four kinds of problem.

- **Nothing to report on locked projects.** A FastAPI project whose `uv.lock` pinned 0.127.0 got
  `DT4001` in every world and no findings, while an unpinned one was analyzed normally. Only the
  exact oracle versions, FastAPI 0.141.1 and Dishka 1.10.1, were accepted.
- **Data directories.** Repositories keep programs that are data: Deadtrace's own `corpus/` and
  `fixtures/`, test inputs, generated code. `report-exclude` hides findings but keeps them in the
  analysis, so their applications rooted worlds and their guards made worlds partial.
- **False findings** of unused-looking code that runs: methods of test mocks that replace
  objects from outside the project (`MockGet.raise_for_status` for a patched `requests.get`),
  fixtures requested with `request.getfixturevalue` or `lf("name")`, fixtures that a `pytest11`
  plugin exports to its users, and CLI commands, which were only conservatively reachable, so
  that code only they use could never be reported.
- **Cost.** On the monorepo the solver took 119 seconds, 87 of them in the tests world, marking
  all 32,552 nodes again for each of 4,760 unresolved fixtures, and the pytest model built one
  retention fact per test and visible fixture.

## Decision

1. **Supported version ranges.** FastAPI `>=0.100,<1` and Dishka `>=1.0,<2` are supported for the
   modeled subset. A pinned version in the range but not oracle-tested adds `DT4002`, which is
   reported and does not weaken a world; a version outside the range adds `DT4001`, which weakens
   every world as before. The oracle still pins one version of each; testing more is ORACLE-02.
2. **`exclude`.** `[tool.deadtrace].exclude` lists glob patterns, over paths relative to the scan
   root, of files that are not source. They are left out of the source universe and listed in the
   report as `source_universe.excluded_files`. Excluded code can protect nothing, so the option is
   for data the project never runs. An empty list does not change the configuration digest.
3. **Test stand-ins.** A method called on a value from outside the project may run a method of
   that name of a class in test code, since tests patch such values with stand-ins. Like ADR-0017's
   rule for typed receivers, this only adds reachability to test code.
4. **Fixtures requested at run time.** `request.getfixturevalue("name")` requests the fixture; a
   computed name may request any fixture the caller sees. `lf("name")` and `lazy_fixture("name")`
   in `parametrize` values request the fixture for the test.
5. **Plugin exports.** Fixtures of a `pytest11` plugin module are roots of its world, with its
   hooks: its users request them.
6. **CLI commands** (`cli.commands`, revision 1). `@app.command()`, `@app.callback()`, and
   `@app.result_callback()` on a module-level `typer.Typer()` are reached from the module;
   `@group.command()` and `@group.group()` on a `@click.group()` function are reached from the
   group.
7. **Loaded modules and managers.** `import_module(x.__module__)`, and `__name__` or
   `__package__`, import a module that is loaded already and add no boundary. The target of
   `with open(...) as f` or of a manager from outside the project is a value from outside it.
8. **Rootless projects** report `DT3004` with what was looked for, instead of `DT3001` for the
   internal placeholder root.
9. **Cost.** A world marks each distinct boundary target set once; equal sets share one tuple.
   Crossing a boundary marks its targets conservative whatever the source's reachability, so the
   result is identical. The pytest model no longer records that each fixture is visible to each
   test; only production worlds read retention, and they reach tests only by over-approximation.

`MODEL_REVISION` becomes `python-fastapi-dishka/12`.

## Consequences

- The locked FastAPI project reports 16 findings, each confirmed against the source.
- With `exclude = ["corpus/**", "fixtures/**"]`, Deadtrace's own scan is complete and reports one
  finding, `unmet_targets`, production code only its tests use.
- On the monorepo, the solver takes 43 instead of 119 seconds and the pytest stage 0.6 instead
  of 5.6 seconds on its largest service. The whole scan still needs about 100 seconds and 2.2 GiB
  for 624k lines, beyond the 50k-line budget; the per-module syntax trees that ADR-0007 keeps are
  the remaining memory lever. Most of its code is protected by a few dynamic imports and
  unknown-receiver calls in build scripts, which `doctor` names.
- `corpus/frameworks/cli_commands` records Typer and Click; unit tests cover each other rule.
- The version policy is a claim about FastAPI and Dishka behavior that the oracle checks for one
  version only. A behavior change inside the range is a model bug to record as a known
  violation.
