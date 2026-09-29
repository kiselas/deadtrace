import _lazy


def unused() -> str:
    return "never called"


def main() -> None:
    print(_lazy.EXPORTS)


if __name__ == "__main__":
    main()
