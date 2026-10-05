# Finite local attribute names with an unknown-write control

The script constructs `First` and selects `run` or `other` with a conditional expression.
An immutable string alias retains that selection after the original variable is overwritten.
Both selected methods may run. `First.unused` has no caller and must remain a candidate.

The second receiver deliberately has an unknown name on one branch. Both of its methods may
run; retaining only the initial `run` string would be unsafe. These expectations follow from
the target's Python behavior, independently of analyzer output. Target code is parsed, never run.
