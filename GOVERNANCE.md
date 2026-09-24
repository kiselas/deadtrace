# Governance

Deadtrace uses maintainer-led governance during pre-alpha.

Maintainers set scope, review changes, make releases, and protect the analysis contract. Design
decisions are recorded as ADRs in `docs/adr/` and evaluated against user value, false-positive
risk, independent testability, maintenance cost, and compatibility.

Routine changes may be merged after review and required checks. Changes to semantic invariants,
the trust boundary, licenses, governance, or stable schemas require explicit maintainer approval
and a recorded decision. Experimental work may be declined even when technically sound if it
widens the active milestone or lacks a realistic evaluation case.

As the contributor base grows, this document should be replaced by a governance model that names
maintainer nomination, voting, conflict resolution, and succession rules.
