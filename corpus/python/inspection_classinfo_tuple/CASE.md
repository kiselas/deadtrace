# Inspection of a literal class-info tuple does not invoke ordinary methods

Python's builtin isinstance accepts a recursively nested tuple of types as classinfo. Inspecting
`value` against `Checked` does not instantiate Checked or call its ordinary `idle` method. Nothing
else references `idle`, so it remains a removal candidate. Passing `(Escaped,)` to an unknown
consumer is different: that consumer may construct the class and call `run`; it must be protected.
These source-level expectations are independent of scanner output. The scanner never executes the
target. Custom metaclass inspection hooks are separately protected and tested, not assumed absent
from Python semantics.
