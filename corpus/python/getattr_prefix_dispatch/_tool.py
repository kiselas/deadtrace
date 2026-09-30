class Serializer:
    def save(self, obj: object) -> int:
        name = "save_" + type(obj).__name__
        return getattr(self.__class__, name)(self, obj)

    def save_int(self, obj: int) -> int:
        return obj

    def save_str(self, obj: str) -> int:
        return len(obj)

    def other(self) -> int:
        return 3


def main() -> None:
    print(Serializer().save(1))


if __name__ == "__main__":
    main()
