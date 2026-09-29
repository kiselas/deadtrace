import _lib


def check_factory() -> None:
    class FromFactory(_lib.Draft7):
        pass


def check_parameter(base: type) -> None:
    class FromParameter(base):
        pass


def check_call() -> None:
    class FromCall(_lib.create()):
        pass


def check_plain() -> None:
    class Plain:
        pass


if __name__ == "__main__":
    check_factory()
    check_parameter(_lib.Draft7)
    check_call()
    check_plain()
