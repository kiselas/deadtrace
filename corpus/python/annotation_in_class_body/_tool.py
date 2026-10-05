class Base:
    def __init__(self, **kwargs: object) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


class Request(Base):
    class Item(Base):
        competency_id: int
        position: int

    class Row(Base):
        text: str

    class Unused(Base):
        pass

    items: list[Item]

    def head(self) -> Row:
        return self.Row(text="first")


def main() -> None:
    print(Request(items=[]).head())


if __name__ == "__main__":
    main()
