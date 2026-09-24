# Alternative imports and definitions

`main` binds `speedup` by `from fast import speedup` in a `try` block, falling back to
`from slow import speedup` on `ImportError`, and defines `clear_screen` differently on
each branch of a platform check. Either binding may be the one that runs, so reporting
`fast.speedup`, `slow.speedup`, or either `clear_screen` as unreached is unsafe.
`fast.unused_fast` is never called and must stay a candidate.

Recorded as a known violation of the analysis contract (ADR-0006) and met from model
revision `python-fastapi-dishka/7` (ADR-0010).
