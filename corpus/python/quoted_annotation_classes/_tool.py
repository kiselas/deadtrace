from typing import Literal, TypedDict


class Behaviour(TypedDict):
    mode: str


class Options(TypedDict):
    depth: int


class Wrapped(TypedDict):
    inner: str


class Named(TypedDict):
    value: str


class Unused(TypedDict):
    other: str


def collect(options: "Options") -> "Behaviour":
    return {"mode": str(options["depth"])}


def wrap(items: list["Wrapped"], kind: Literal["Unused", "Other"]) -> "dict[str, Named] | None":
    return None


if __name__ == "__main__":
    collect({"depth": 1})
    wrap([], "Other")
