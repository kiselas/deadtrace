# A store does not invoke unrelated instance methods

The script constructs Stored and calls read. The initializer writes the integer 1 to value
using the builtin object.__setattr__. There is no descriptor at that name, and idle is never
retrieved or called. Stored.idle is independently unused; Stored.read is live.

This is a recall gap, not an unsafe candidate. Pin the existing missed target before refining
the store consumer. The expectation follows Python's attribute-store contract, not the
scanner's output. Custom descriptors and shadowed object calls require separate live controls.
