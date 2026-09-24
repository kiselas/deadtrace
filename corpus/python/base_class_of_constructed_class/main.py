class Base:
    def describe(self) -> str:
        return "base"


class Child(Base):
    pass


def unused_control() -> str:
    return "never called"


def main() -> None:
    child = Child()
    print(child.describe())
