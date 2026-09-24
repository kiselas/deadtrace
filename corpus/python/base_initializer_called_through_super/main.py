class Base:
    def __init__(self) -> None:
        self.ready = True


class Child(Base):
    def __init__(self) -> None:
        super().__init__()


def unused_control() -> str:
    return "never called"


def main() -> None:
    print(Child().ready)
