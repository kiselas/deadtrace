def parse(text: str) -> list[str]:
    return _tokenize(text)


def _tokenize(text: str) -> list[str]:
    return text.split()


def not_reexported() -> None:
    pass


def _orphan() -> None:
    pass
