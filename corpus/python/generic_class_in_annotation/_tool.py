from __future__ import annotations

from typing import Generic, Protocol, TypeVar

T = TypeVar("T")


class Box(Generic[T]):  # noqa: UP046
    pass


class Reader(Protocol[T]):
    def read(self) -> T: ...


class Unused(Generic[T]):  # noqa: UP046
    pass


def use(box: Box[int]) -> type[Reader[int]] | None:
    return None


if __name__ == "__main__":
    use(Box())
