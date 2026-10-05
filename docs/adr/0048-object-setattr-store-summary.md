# ADR-0048: Literal builtin object.__setattr__ stores on self

**Status:** Selected, 2026-10-05; independently pin the recall gap on model 31 first.

ADR-0047 diagnostics are complete. Exact-consumer cuts across nine development packages give
typing.cast an upper bound of seven private injected methods (Click four, Typer two, Packaging
one), but many casts return objects from public factories. Removing their guards without
preserving subsequent object consumers can release live methods. Receiver/return escape
infrastructure is deferred rather than treating these cuts as a safety argument.

Select one bounded store summary instead. Cutting object.__setattr__ escaped_class guards
frees one injected Packaging method and none in h11: the earlier nineteen listings were not
nineteen independent gains. The independent object_setattr_store case pins an unused ordinary
method retained by the current store guard. Keep recall gaps separate from safety contract
violations in fixtures/known-violations; use the same manifests and exact unmet-target ratchet,
and move a resolved case to corpus without changing its independent expectations.

For an unshadowed bare builtin object.__setattr__ call with exactly three positional arguments,
no keywords or stars, self as its first argument and a literal string name, account for self
as the receiver of an attribute store rather than an arbitrary method-calling consumer.
Retain the receiver class and existing implicit descriptor/metaclass hooks. Preserve existing
escape protection for the stored value; this does not infer field provenance. Reject module,
local/enclosing bindings, star imports and visible qualified writes that invalidate the
builtin identity. All other shapes retain the previous guard.

The Python 3.12 data model documents object.__setattr__ for writes and descriptor __set__
callbacks: https://docs.python.org/3.12/reference/datamodel.html#object.__setattr__ .
Test setter callbacks, stored callable/instance values, shadowing and unsupported call shapes.
No target execution, dependencies, public schema or source-universe expansion is introduced.
After implementation the model revision becomes 32 and python.direct-flow becomes 7.
