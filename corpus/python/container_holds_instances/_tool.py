class State:
    def report(self) -> str:
        return "state"

    def forgotten(self) -> None:
        pass


class Registry:
    def __init__(self) -> None:
        self.entries: list[Registry] = []

    def summary(self) -> str:
        return "registry"

    def forgotten(self) -> None:
        pass

    def keep(self, entry: "Registry") -> None:
        self.entries.append(entry)


def load(rows: list[int]) -> list[State]:
    states = []
    for row in rows:
        state = State()
        states.append(state)
        del row
    return states


def main() -> None:
    registry = Registry()
    registry.keep(Registry())
    for state in load([1, 2]):
        state.report()
    for entry in registry.entries:
        entry.summary()


if __name__ == "__main__":
    main()
