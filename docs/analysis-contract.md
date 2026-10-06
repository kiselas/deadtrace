# Alpha analysis contract

Deadtrace 0.1.0a2 analyzes Python source statically with scanner model 35. It never imports,
executes, installs or contacts target code during ordinary scan. The CLI reads source/configuration
and writes only explicitly requested reports, baselines and diagnostic artifacts.

Source discovery and report visibility are distinct. Excluding data from the source universe
removes its protective influence; report exclusions only hide presentation. Discovery skips virtual
environments, installed packages and tool directories and reports those exclusions.

Each execution world has explicit or discovered roots. Resolved reachability, conservative
reachability and declaration retention are distinct. Unknown dynamic behavior protects the code
it may affect, potentially the whole world. Invalid inputs, unsupported dependency versions and
unresolved assembly cannot justify stronger negative findings. A complete world means the modeled
contract is satisfied under the report's inputs; it does not prove all possible Python executions.

RCH001-RCH004 findings group code for review. They are never permission to delete code. Review
deployment roots, external contracts, input completeness and dynamic behavior before any removal.
The scanner has no automatic deletion or execution mode. Tests/oracles may execute only the
trusted reference programs explicitly maintained for verification, outside scanner paths.

Saved explanations use the saved report. Baselines acknowledge reviewed findings without altering
the graph. Comparisons expose model/config/support/world incompatibilities. Exit 0 means completed,
1 means an explicitly requested finding policy failed, and 2 means an operational or required
completeness/comparability failure; 2 takes priority.

Inventory schema 0 and semantic schema 1 are alpha interfaces. Determinism applies to canonical
reports for identical inputs, excluding explicitly volatile benchmark measurements. See accepted
[ADRs](adr/README.md), [support limits](support-matrix.md) and [release acceptance](releasing.md).
