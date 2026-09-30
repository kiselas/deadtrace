from abc import ABC, abstractmethod


class Handler(ABC):
    @abstractmethod
    def run(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def describe(self) -> str:
        raise NotImplementedError


class Cancel(Handler):
    def run(self) -> str:
        raise NotImplementedError("cancel jobs are launched elsewhere")

    def describe(self) -> str:
        return "cancel"

    def extra(self) -> str:
        return "extra"


def main() -> None:
    handler = Cancel()
    print(handler.describe())


if __name__ == "__main__":
    main()
