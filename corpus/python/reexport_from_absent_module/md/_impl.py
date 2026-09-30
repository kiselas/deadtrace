class MultiDict:
    def add(self, key: str, value: str) -> None:
        self._items = [(key, value)]

    def _unused(self) -> int:
        return 1


def getversion(md: MultiDict) -> int:
    return 1


def _unused_helper() -> int:
    return 2
