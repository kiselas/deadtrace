import dataclasses


@dataclasses.dataclass
class Order:
    total: int

    def __post_init__(self) -> None:
        self.total = max(self.total, 0)


def unused_control() -> str:
    return "never called"


def main() -> None:
    print(Order(5))
