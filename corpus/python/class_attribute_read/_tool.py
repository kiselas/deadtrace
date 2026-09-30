import enum


class Settings:
    limit = 3

    def unused(self) -> int:
        return self.limit


class Kind(enum.Enum):
    A = 1

    def retired(self) -> str:
        return "retired"


def main() -> None:
    print(Settings.limit, Kind.A.value)


if __name__ == "__main__":
    main()
