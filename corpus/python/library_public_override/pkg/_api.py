from abc import ABC, abstractmethod


class Process(ABC):
    @abstractmethod
    def terminate(self) -> None: ...

    @abstractmethod
    def kill(self) -> None: ...


def open_process() -> Process:
    from pkg._impl import Impl

    return Impl()
