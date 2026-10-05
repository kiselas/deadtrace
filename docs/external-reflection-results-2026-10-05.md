# External reflection: safety fix and nominal refinement, 2026-10-05

Final implementation: model 26, commit `bff2823`. The preceding model 25 implementation is
`ea6f8d0`. [ADR-0035](adr/0035-external-reflection-provenance.md) records the independent violation;
[ADR-0036](adr/0036-localize-external-value-reflection.md) fixes it;
[ADR-0037](adr/0037-standard-nominal-reflection-families.md) refines the guard after development
measurements exposed a recall regression.

## What changed

A reflected method retrieved from an externally annotated parameter may belong to a project
subclass. Previously, storing and calling that value could report the method as dead, while calling
the same lookup immediately opened a whole-project guard. The frontend now propagates explicit
external annotation provenance and handles both forms consistently.

For supported Python 3.12 nominal families (pathlib paths and logging.LogRecord), the guard covers
possible project subclasses, their inherited members, opaque external bases and test stand-ins.
Standard roots with disjoint ancestry and plain unrelated classes can be excluded. Rebinding,
conditional imports, computed bases and unknown values retain protection. Unrecognized nominal
origins use a broader guard. This uses shipped semantic data, not target/dependency execution.

Annotations remain an analysis input contract, not runtime enforcement. Names from mutable
dictionaries are not treated as constants. No report/config schema or dependency changes were made.

## Independent evidence and checks

Before any fix, commit `a37e5b7` pinned exactly `_tool.py:ProjectPath.check` in the
`external_reflection_value` known-violation case. The unchanged expectations now pass in corpus.
Archived model 24 confirms that it reports this method and the unrelated control as candidates.
The independent immediate-call case instead loses its unused-function control on model 24.
Archived model 25 loses the unrelated-method control of `nominal_external_reflection`.
Model 26 passes all three cases. These targets are parsed, never executed.

Added 51 tests since model 24, covering direct/stored/literal reflection, conditional and string
annotations, aliases, indirect bases, stand-ins, escaped functions, unknown writes, loop state,
nominal joins, project mixins, rebinding, builtin shadows and computed/conditional bases.
Verification passed:

- Ruff check/format and mypy for Windows and the Linux target, 59 source files.
- **459 tests passed, two skipped, 93.11% branch coverage**. The skips concern Windows symlink
  privileges and the empty known-violation parameter set.
- Seed validator: 6 cases/12 targets. Corpus: **118 cases/416 targets**, all semantic cases passed.
- Offline isolated source/wheel build and wheel smoke outside the checkout. The smoke explicitly
  verifies installed model 26, then checks determinism, artifacts, input errors and no target
  execution. Runtime Linux CI remains pending.

## Clean-commit field measurements

All package runs used fieldkit. Final development scan:
`20261005-145631-r26-r26-nominal-reflection`; seed-7 injection:
`20261005-145719-r26-inject7-r26-nominal-reflection`. Both ran a clean `bff2823` tree.

| Package | Findings, model 24 → 26 | Injected hits, model 24 → 25 → 26 |
|---|---:|---:|
| Rich 15.0.0 | 1 → 1 | 58/76 → 12/76 → 58/76 |
| Pydantic 2.13.5 | 0 → 0 | 0/76 → 0/76 → 0/76 |
| Typer 0.27.2 | 5 → 5 | 55/76 → 55/76 → 55/76 |
| Pluggy 1.6.0 | 2 → 2 | 35/42 → 35/42 → 35/42 |
| Packaging 26.3 | 2 → 2 | 57/76 → 57/76 → 57/76 |

Model 25's clean-commit injection batch is `20261005-143718-r25-inject7-r25-external-reflection`.
It detects 159/346 (46.0%); it was refined after this regression, rather than presented as an
improvement. Final model 26 returns to **205/346 (59.2%)**. There are zero NEW/LOST findings versus
model 24, six inherited true and four inherited false labels, zero unsure/unverified development
findings. These labels are not a fresh independent precision audit, and injection recall is not
recall over all dead code. No speed claim is made.

Holdout subset batch `20261005-145729-r26-r26-nominal-reflection-subset`: sniffio, shellingham,
uritemplate, simple_websocket and smbclient. All five scans complete with zero findings and zero
NEW/LOST versus model 24. Zero findings provide no precision/recall estimate. The broader historical
holdout is not newly verified. Holdout findings were not used to tune this refinement.

## What the Pydantic investigation actually established

The Path parameter already resolves through its TYPE_CHECKING import. The original broad lookup
was inconsistent with ordinary receiver handling. Its boundary is now localized, but its possible
opaque-base members and normal package execution can still reach a later broad boundary.

The archived model-26 derivations show the injected module function in
`pydantic/deprecated/class_validators.py` protected directly by
`PydanticDescriptorProxy._call_wrapped_attr`, not by a direct whole-graph lookup in `path_type`.
The current field `held_by` names the **first** boundary crossed along the selected derivation;
that alone can misleadingly suggest that the entire problem is the initial Path lookup.

Source inspection of `_decorators.py:165–208` shows a wrapped descriptor, setter/deleter names and
`partial(self._call_wrapped_attr, name=attr)`, followed by dynamic `getattr(self.wrapped, name)(func)`.
This requires argument/callback/field provenance. A keyword bound by partial can be overridden by
a caller, so merely copying its two initial strings into the callee is not a sufficient safety proof.
The keyword override behavior is specified by the
[Python 3.12 partial API](https://docs.python.org/3.12/library/functools.html#functools.partial).

The next bounded proposal should improve guard-chain diagnostics and specify independent cases
for partial keyword overrides, escaping callbacks, descriptor aliases and unknown external callers
before implementing interprocedural summaries. The safety fix is real; measured package detection
has **not** improved, the four historical false findings remain, and market-leading quality is not
established.
