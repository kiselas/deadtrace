# Alpha architecture

The scanner collects stable source snapshots and parses with Python's stdlib ast. Inventory and
semantic consumers share parsed input. The Python frontend creates symbols, references and bounded
receiver/name flow. Framework capabilities add roots, registrations and conservative boundaries;
target frameworks are not scanner runtime dependencies.

The analyzer plans execution worlds, computes resolved and conservative graph reachability and
retention, then constructs deterministic findings with derivations. Serializers emit text/JSON;
saved-artifact readers validate reports, explanations, baselines and comparisons independently of
the current project. Machine output uses stdout and diagnostics use stderr.

The trust boundary ends at static source/configuration and bounded saved JSON input. Source is
data, never imported as a plugin. Framework rules are repository-owned capabilities, not target
loaders. The separate trusted oracle environment executes only the included reference application
for tests. Release scripts inspect distribution metadata without executing packaged target source.

Scanner model revisions identify semantic changes; capability versions identify affected models.
Alpha schemas are documented in source and guarded by tests. Detailed decisions and tradeoffs,
including shared parsing, graph lookups and conservative propagation, live in [ADRs](adr/README.md).
