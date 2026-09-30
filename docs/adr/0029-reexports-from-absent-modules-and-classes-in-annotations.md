# ADR-0029: Re-exports from absent modules and classes in annotations (model revision 22)

**Status:** Accepted, 2026-09-30.

## Context

The findings of the eleventh pass's batch were verified member by member: 1614 members, read by
nine reviewers against the sources, 1110 true, 503 false. Most false findings are of kinds already
recorded as limitations (a test suite that a package ships for its consumers, functions that a
skill's documentation tells the reader to import). Two mechanisms recorded as fixed were still
reported, and one was new:

- **A re-export whose other branch has no source.** `multidict/__init__.py` imports its classes from
  `._multidict_py` when extensions are off and from `._multidict`, a compiled module, otherwise.
  ADR-0028 follows every import of a name when a project name is resolved through the module, but
  the public API of a package (the `library` and `exports` worlds) still took the last import of each
  name, which named the compiled module and resolved to nothing. Every class of the pure-Python
  module was reported: 140 findings.
- **An attribute chain in an annotation.** `def fire(self, data: Meta.Models.EventDataType)`, where
  `EventDataType` is an alias assigned in the body of the nested class `Models`. ADR-0027 counts an
  attribute read as a use of the class it is read from, but an annotation resolved the whole chain
  or nothing, so `Models` was reported.
- **A bare name in the body of a class.** `class Request: class Item: ...; items: list[Item]`, and a
  method `def head(self) -> Row` where `Row` is nested in the same class. Python evaluates both in
  the body of `Request`, where `Item` and `Row` are its members; the analyzer looked them up at the
  module level and found nothing.

## Decision

1. **API worlds follow every import.** When a package's `__init__` binds a name by more than one
   import, one of them conditionally, the `library` and `exports` worlds resolve each import and take
   every project definition found. A branch whose module is absent adds nothing.
2. **Annotations use the classes a chain goes through.** A dotted name in an annotation that resolves
   to no definition is shortened from the right until it does; the class it reaches, and the classes
   that own it, are used. Names that resolve to no class still use nothing.
3. **Class bodies resolve their own names first.** An annotation in the body of a class, or in the
   signature of one of its methods, looks a bare name up as a member of that class before the
   module. Enclosing classes are not consulted, as in Python.

`MODEL_REVISION` becomes `python-fastapi-dishka/22`.

## Consequences

- Corpus cases fail on revision 21: `python/reexport_from_absent_module`,
  `python/annotation_reads_class_attribute`, `python/annotation_in_class_body`. Accepted.
- The field projects and the installed packages report the same findings as before, apart from the
  141 members above, which are no longer reported. Recorded in the field ledger with the batch of this
  revision.
- Not changed, recorded as limitations: a test suite a package ships for third-party consumers
  (`alembic.testing.suite`, 163 members), definitions that documentation alone tells a reader to
  import (92), standalone scripts without a main guard that no deployment file names (3).
