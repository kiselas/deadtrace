class Meta(type):
    def __new__(mcs, name: str, bases: tuple[type, ...], namespace: dict[str, object]) -> type:
        return super().__new__(mcs, name, bases, namespace)


if __name__ == "__main__":
    print(Meta)
