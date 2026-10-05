# ADR-0045: Pin the public factory return API violation

**Status:** Accepted, 2026-10-05.

Model 30 can report a private-module class's public method as dead even when an exported
factory declares that class as its return type. External consumers can call `make().run()`.
Pin the independent public_return_api case before any fix, with a private method as a control.
The only next semantic milestone is bounded automatic API closure through declared returned
project objects. Public-field closure (ADR-0044) is complete; inspection aliases remain deferred.
No target execution, schema or dependency changes are authorized by this record.
