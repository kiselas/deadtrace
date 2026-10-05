# Pydantic recall diagnosis and review, 2026-10-05

The initial selected-path hypothesis in the model-31 results document is superseded by full
boundary replay. Removing exposure from default_ignored_types does not explain this package's
zero recall: PydanticDescriptorProxy._call_wrapped_attr has a legitimate alternative path through
the dataclass post-init hook and a stored partial. Its reachability must remain protected.

## Reproduced facts

The diagnostic fieldkit explain command replays the model-31 injection run with identical
analyzer source, target source and config digests. The baseline and all cuts finish within budget.
One crossed dynamic_attribute_dispatch boundary in _call_wrapped_attr has no explicit targets;
the existing core contract therefore protects every graph node. Removing its source/domain
boundary group leaves 57 of 76 injected definitions unreached. A hypothetical replacement by
class-owned definitions, gated on their classes, leaves only 12 module-function injections
unreached. A reached deserialization boundary opens the class gates; the remaining injected
classes and their members stay protected.

These are diagnostic re-solves, not scanner improvements or deletion verdicts. The production
scanner remains model 31, with measured injection recall 474/721 and Pydantic 0/76. The research
report's nine other package analyses also find no crossed whole-graph guard in their selected
production world; those classifications describe listings, not an exhaustive safety audit.

The archived report truncates explanations at 2000; this run has 4092 derivations before truncation.
The old trace cannot establish absence of other paths. The injection ledger's held_by records the
first conservative transition along a selected path, not necessarily the immediate target guard.

## Limits of the proposed implementation

The attribute-universe experiment does not establish that self.wrapped is non-module. Applying
it indiscriminately releases a live module function when the field stores sys.modules[__name__].
This counterexample is covered by a diagnostic-tool regression, without executing target code.

The research algorithm requires provenance for every relevant field write, but the motivating
Pydantic field is populated through a generated dataclass initializer and later reassigned from
getattr(self.wrapped, name)(func), an unresolved return. Its declared type is an assigned, quoted
Union alias containing Callable, property, classmethod and staticmethod. Current nominal field
inference does not resolve that contract. A Callable annotation is a structural callability
contract, not proof that a value is not a module; modules may use a custom ModuleType subclass.
Unknown writes and arbitrary returned values must retain conservative fallback.

The suggested +12 is therefore a result of an unqualified hypothetical substitution, not a promised
gain from the proposed qualified algorithm. No source name specific to Pydantic justifies narrowing.
Stored project functions, inherited attributes, descriptors, dynamic field writes and module-valued
alternatives require controls. The correctness of stored-value escape tracking must be verified,
not assumed from one direct-assignment example.

Partial keyword bindings cannot be treated as permanently fixed: call-site keywords override them.
See [functools.partial](https://docs.python.org/3.12/library/functools.html#functools.partial),
[module customization](https://docs.python.org/3.12/reference/datamodel.html#customizing-module-attribute-access)
and [callable annotations](https://docs.python.org/3.12/library/typing.html#annotating-callable-objects).

## Next bounded work

The next semantic decision must define an explicit receiver provenance contract before narrowing
reflection: distinguish known project instances, known modules, stored callable values and unknown
alternatives; propagate field stores/loads and retain unknown for unsupported writes. Establish
independent controls for module receivers, properties returning modules, module-valued branches,
generated initializers, constructor parameters and reflective reassignment. Measure which of the
real field's origins this supports before claiming package recall gains.

Class-container consumer summaries remain a separate candidate with evidence on other packages.
Metadata types and dict keys can be retrieved and used later; a no-callback store is not proof that
the stored class never escapes or is constructed. Such summaries need read/escape controls.

This cycle finishes the inherited research tooling and corrects the diagnosis. It does not change
scanner semantics, public schemas, dependencies, corpus expectations or verdict provenance.

## Validation

The field diagnostic suite passes 19 tests, including a module-receiver counterexample and
incomplete-cut handling; new tool files pass Ruff checks/format. Main-repository gates pass:
Ruff check/format (573 files), mypy Windows/Linux targets (59 files each), pytest 510 passed with
two expected skips and 93.21% coverage; seed validator 6 cases/12 targets, corpus 123 cases/426
targets. Offline source/wheel build and isolated installed-wheel smoke with the model-31 assertion
and no-target-execution sentinel pass. A stalled initial build was restarted. Linux runtime CI
was not executed locally. The ten-package scanner measurements remain the model-31 results.
