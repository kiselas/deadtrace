from collections.abc import Callable


class Messages:
    def welcome(self) -> str:
        return "welcome"


class MailCore(Messages):
    def send(self, generator: Callable[[], str] | None) -> str:
        return generator() if generator is not None else ""


def send_email(name: str) -> str:
    core = MailCore()
    method = getattr(core, name, None)
    return core.send(method)


class Visitor:
    def visit(self, kind: str) -> str:
        return getattr(self, "visit_" + kind)()


class Printer(Visitor):
    def visit_name(self) -> str:
        return "name"


def forgotten() -> None:
    pass


if __name__ == "__main__":
    print(send_email("welcome"), Printer().visit("name"))
