# ADR-0101: Overridden stub methods are interface declarations

**Status:** Accepted, 2026-10-12; model revision 84.

A base class often declares the hooks its subclasses implement:

```python
class BaseParser:
    def _validate_input(self, path):
        raise NotImplementedError


class EdcdParser(BaseParser):
    def __init__(self, path):
        self._validate_input(path)

    def _validate_input(self, path): ...
```

Every call resolves to an override, so the declaration never runs and was reported. Reviewers judge
it in use: it is the interface the subclasses implement, and deleting it breaks the contract and
type checking. On the reviewed cohorts b-g (model 81), findings made only of such methods were 3
false and no true one; a looser test (any other method of that name anywhere) would have hidden 13
true findings.

The blocked layer (ADR-0071) gets a fifth reason, `interface_declaration`: every member of the
finding is a method whose body is only a docstring, `pass`, `...` or `raise NotImplementedError`,
or that is decorated `abstractmethod`, and some project subclass of its class, directly or not,
defines a method of the same name. The analysis is unchanged; the finding moves to
`blocked_findings`.

MODEL_REVISION becomes `python-fastapi-dishka/84`.
