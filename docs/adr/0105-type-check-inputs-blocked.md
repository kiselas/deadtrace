# ADR-0105: Type checker inputs under tests are blocked

**Status:** Accepted, 2026-10-12; model revision 88.

Libraries test their type annotations with files that a type checker reads and nothing runs:
`tests/typing/api_pass.py` checked by `mypy tests/typing`, a `tests/type_checking.py` whose
functions sit under `if TYPE_CHECKING:`. Their definitions are unreachable by design and reviewers
judge them in use. On the reviewed cohorts b-g (model 81), findings made of members in such files
were 8 false and no true one, in three projects.

The blocked layer (ADR-0071) gets a sixth reason, `type_check_input`: a member under a test
directory (`test`, `tests`, `testing`) whose path has a directory or module named `typing`,
`type_checking`, `typecheck` or `typesafety`, optionally with a `_suffix`. Modules with these names
outside test directories are production code and are not blocked.

MODEL_REVISION becomes `python-fastapi-dishka/88`.
