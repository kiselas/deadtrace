MOVED = {"OLD_LIMIT": 10}


def __getattr__(name: str) -> int:
    try:
        return MOVED[name]
    except KeyError:
        raise AttributeError(name) from None


def __dir__() -> list[str]:
    return sorted(MOVED)


def unused() -> None:
    pass
