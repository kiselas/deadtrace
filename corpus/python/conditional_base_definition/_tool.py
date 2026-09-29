import sys

if sys.platform == "win32":

    class Base:
        kind = "windows"

else:

    class Base:
        kind = "posix"


class Model(Base):
    pass


def unused() -> str:
    return "never called"


def main() -> None:
    print(Model.kind)


if __name__ == "__main__":
    main()
