class Money:
    def __init__(self, amount: int) -> None:
        self.amount = amount

    def __str__(self) -> str:
        return f"{self.amount} EUR"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Money) and other.amount == self.amount

    def __hash__(self) -> int:
        return hash(self.amount)


def unused_control() -> str:
    return "never called"


def main() -> None:
    print(Money(1), Money(1) == Money(2), {Money(3)})
