# Known violations

Each case here is a small target program whose independent expectation Deadtrace does not meet yet:
in a complete world, it reports code that may run as an unreached candidate. The cases record
contract violations; they are not future features.

A case has the same files as a seed case: `CASE.md` explains the safe outcome and why the unsafe one
is unsafe, `CASE.toml` names the lexical targets and their expectations, and `pyproject.toml`
configures the world so the expectation is checked semantically. There is no `[analysis]` table,
because the limitation codes a fix will produce are not known in advance.

Expectations follow the corpus vocabulary. `not_candidate` is a safety-only expectation: the target
must be in no finding, whether a fix makes it resolved, conservative, or part of a weakened world.
Where a fix must stay local, a `candidate` control target that nothing references keeps the case
from being satisfied by weakening the whole world.

`tests/test_known_violations.py` pins exactly which targets are unmet today. A fix removes entries,
a regression adds them, and the pinned list changes in the same commit. A case with no unmet target
moves to `corpus/` with the `[analysis]` table of the model revision that fixed it.

These programs are data. Deadtrace's scanner never imports or executes them, and Ruff ignores this
directory.
