# ADR-0067: A use between two definitions reaches the earlier one

**Status:** Accepted, 2026-10-07; model revision 49.

A name defined twice resolved to its last definition everywhere. Statements of one body run in
order, so a use between the two definitions reaches the first: `form = F()` before a second
`class F` statement, or `patch.object(..., new=post_json)` before `post_json` is redefined. Those
first definitions were reported as unreached (3 reviewed findings).

A plain name used in the same body that defines it (a function body, or module top level for
module names) now resolves to the last definition that starts before the use, or to the last one
when none does. A name used inside a nested function still resolves to the last definition of the
enclosing scope, since the nested body runs only after the enclosing one has finished: a `helper`
defined twice at module level and called from a function stays a finding for its first definition.

The case validator now honours `occurrence` on a target, so a case can tell two definitions of one
name apart.

The case `corpus/frameworks/use_before_redefinition` fails on revision 48.

MODEL_REVISION becomes `python-fastapi-dishka/49`.
