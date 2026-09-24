from typing import overload


@overload
def parse(value: int) -> int: ...


@overload
def parse(value: str) -> str: ...


def parse(value: int | str) -> int | str:
    return value


class Reader:
    @overload
    def read(self, size: int) -> bytes: ...

    @overload
    def read(self) -> str: ...

    def read(self, size: int | None = None) -> bytes | str:
        return b"" if size is not None else ""


@overload
def unused(value: int) -> int: ...


@overload
def unused(value: str) -> str: ...


def unused(value: int | str) -> int | str:
    return value


def main() -> None:
    parse(1)
    Reader().read()
