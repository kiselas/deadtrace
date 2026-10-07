def build() -> list[object]:
    class Form:
        kind = "first"

    first = Form()

    class Form:
        kind = "second"

    return [first, Form()]


def helper() -> int:
    return 1


def use() -> int:
    return helper()


def helper() -> int:  # noqa: F811
    return 2


def unused() -> str:
    return "never called"


def main() -> None:
    print(build(), use())


if __name__ == "__main__":
    main()
