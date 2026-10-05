# ADR-0046: Follow declared public return contracts in automatic API discovery

**Status:** Accepted, 2026-10-05. Resolves ADR-0045; model revision 31.

The automatic library/package-export API worklist follows project classes declared as return
types of exposed functions and methods (including property getter symbols). These classes expose
their public methods, fields and project bases using the existing closure. Root deduplication
terminates return cycles. Both arms of project conditional imports are preserved.

Support nominal/quoted annotations, PEP-604 unions, imported typing Union/Optional/Type and
Annotated (only its first argument), including typing aliases. For arbitrary generic annotations,
expose only a resolvable project outer class. Do not treat Callable input types, container element
types, Literal strings or Annotated metadata as directly returned objects. Return annotations
are source contracts, not runtime validation. Existing pytest fixture discovery is unchanged.

Unannotated return inference, type aliases expressed as assignments, Self, builtin type[T],
container/iterator element exposure and unavailable subclasses remain outside this bounded rule.
Explicit configured worlds are unchanged. No target is imported/executed. Report/config schemas
and dependencies are unchanged; python.library-roots rises to 3 and the model to 31.

Move the independently pinned public_return_api case into corpus without changing its targets.
Controls cover private methods, parameter types, Callable inputs, metadata, literal strings,
quoted/aliased/conditional types, chained returned methods/fields, export worlds and cycles.
Required gates and measured field results are recorded separately after verification.
