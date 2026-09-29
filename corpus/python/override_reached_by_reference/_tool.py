import functools


class Root:
    def first(self) -> None:
        pass


class Handler(Root):
    def run(self) -> None:
        schedule(self.first)
        functools.partial(self.second, 1)()

    def first(self) -> None:
        pass

    def second(self, value: int) -> None:
        pass


class Plugin(Handler):
    def first(self) -> None:
        pass

    def second(self, value: int) -> None:
        pass

    def unused(self) -> None:
        pass


class Sibling(Root):
    def first(self) -> None:
        pass


def schedule(callback) -> None:
    callback()


def make() -> Handler:
    return Plugin()


if __name__ == "__main__":
    make().run()
