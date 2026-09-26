from enum import Enum


class Status(Enum):
    ACTIVE = "active"


class Level(Enum):
    HIGH = 3


class Unused(Enum):
    NONE = 0


class Settings:
    DEFAULT_LEVEL = Level.HIGH.value


def current() -> str:
    return Status.ACTIVE.value


if __name__ == "__main__":
    print(current(), Settings.DEFAULT_LEVEL)
