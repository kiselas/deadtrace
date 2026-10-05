# ADR-0039: Preserve callables retrieved with literal getattr

**Status:** Accepted, 2026-10-05. Resolves ADR-0038; model revision 27.

## Decision

Use the existing localized reflected-value boundary for constant names as well as computed names.
Previously an early return skipped literal names before enumerating known project receiver or
module members. Removing that return allows the existing exact string selection to retain the
selected callable. Method lookup includes project MRO ancestors and project subclasses, preserving
overrides under the existing annotation contract. Empty selections produce no whole-graph guard.
The value may escape or run later: this deliberately records conservative reachability, not a
resolved call edge or proof that it actually executes.

The independently specified `stored_literal_reflection` case moves from known violations to corpus
with its original target expectations unchanged. Unit checks cover constructor expressions,
instances, inherited methods, overrides, project modules and missing attributes with defaults.
A separate partial-keyword-override check protects the broad fallback: bound keyword arguments
are overridable by a later caller, as specified in
[Python 3.12 functools.partial](https://docs.python.org/3.12/library/functools.html#functools.partial).

## Scope and limits

Unknown stored receivers retain the previous limitation; this is not an interprocedural value-flow
or heap/descriptor model. External reflection provenance and nominal families remain as in ADR-0036
and ADR-0037. Attribute alias safety still depends on existing escaped-reference handling. No
package-specific rules, target execution, external source reads, dependencies, public schema or
configuration changes are introduced. Model revision alone changes to identify the new semantics.

Pydantic's selected guard chain reaches descriptor reflection through an escaped class reference.
Narrowing it by the initial keywords of partial would be unsound; the remaining recall problem
requires summaries that account for escaping values, caller overrides, descriptor operations and
unknown callers. Archived-chain diagnostics in the private field tool precede any such refinement.
