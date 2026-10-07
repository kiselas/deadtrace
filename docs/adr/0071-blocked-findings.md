# ADR-0071: Blocked findings

**Status:** Accepted, 2026-10-07; model revision 53. Changes the semantic report (additive).

Hand review of 571 findings from three blind cohorts of public projects (`docs/field/`) showed
that a few recognizable forms are mostly false: methods of classes with an external base (20 %
true), code under `examples`, `docs`, `scripts`, `tools` (27 %), public names of a documented or
`__all__`-exporting package (35 %), and names that a configuration or template file mentions
(32 %). No structural slice of the remaining findings is above 71 %, so tuning rules alone does
not raise precision much further; these forms need a different treatment. Industrial
dead-code removers report the same pattern: they hold back what they cannot vouch for and keep a
reason, rather than reporting everything or hiding it silently.

A finding with code RCH001 or RCH004 is *blocked* when any member matches one of these reasons:

- `external_base_hooks`: a method whose owning class has a base that resolves to no project class
  and is not `object`, `Protocol`, `Generic`, `ABC`, or `ABCMeta`;
- `non_production_area`: a member under a directory named `bench`, `benchmark(s)`, `demo(s)`,
  `doc(s)`, `docs_src`, `example(s)`, `playground`, `sample(s)`, `scripts`, or `tools`;
- `public_api`: a public name (no part starting with `_`) of a public module inside a package,
  outside test directories, when the project documents its API (Sphinx `automodule`/`autoclass`/
  `autofunction`/`automethod`, `::: module` of mkdocstrings, `mkapi`) or the module or its package
  lists the name in `__all__`;
- `mentioned_in_config`: the member's last name, at least four characters and not a dunder,
  appears as a word in a `.cfg`, `.conf`, `.env`, `.html`, `.ini`, `.j2`, `.jinja`, `.jinja2`,
  `.toml`, `.xml`, `.yaml`, or `.yml` file, a Makefile, Dockerfile, Procfile or justfile of the
  project. JSON and plain text are not read (reports, fixtures, logs, and requirement lists name
  everything), nor are files that look like deadtrace's own artifacts.

RCH002 and RCH003 are proven by a framework model and are never blocked.

Blocking does not change the analysis. `AnalysisResult.findings` holds the findings that are
shown; `AnalysisResult.blocked_findings` holds the blocked ones with their reasons. The semantic
report adds a `blocked_findings` array, whose entries carry a `blocked` list of reasons, and
`summary.blocked_finding_count`; the schema version stays 1 because readers that ignore unknown
keys see the shown findings exactly as before. Exit codes, baselines, `compare`, and `explain`
see only shown findings. Text output prints a count by reason and, with `--show-blocked`, the
findings. The case validator counts blocked findings as findings, since a case states what the
analysis finds, not what a report shows by default.

Files are read as bounded text (1 MiB each, 5,000 files at most), skipping the directories that
source discovery skips and the configured `exclude` patterns. Nothing is imported or executed.

Measured on the reviewed findings that model revision 51 still reports (cohorts b, c, d):
precision of shown findings 58.3 % without blocking and about 67 % with it, at the cost of 75 of
253 true findings moving from shown to blocked. A blocked true finding is a missed report, not a
wrong one; the reverse error is the one that costs users.

MODEL_REVISION becomes `python-fastapi-dishka/53`.
