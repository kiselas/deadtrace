import ctypes
from typing import NamedTuple


class Point(NamedTuple):
    x: int
    y: int

    @classmethod
    def from_param(cls, value: "Point") -> int:
        return value.x


class Unused(NamedTuple):
    x: int

    @classmethod
    def from_param(cls, value: "Unused") -> int:
        return value.x


def main() -> None:
    function = ctypes.CDLL(None).abs
    function.argtypes = [Point]
