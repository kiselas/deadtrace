import sys
from abc import ABC, abstractmethod


class Strategy(ABC):
    @abstractmethod
    def place(self) -> int: ...


class Wide(Strategy):
    def place(self) -> int:
        return 1


class Narrow(Strategy):
    def place(self) -> int:
        return 2


class Layout:
    def __init__(self, wide: bool) -> None:
        self.strategy: Strategy
        if wide:
            self.strategy = Wide()
        else:
            self.strategy = Narrow()

    def run(self) -> int:
        return self.strategy.place()


class Fast:
    def go(self) -> str:
        return "fast"


class Slow:
    def go(self) -> str:
        return "slow"


class Switcher:
    def __init__(self) -> None:
        self.mode = Fast()

    def reset(self) -> None:
        self.mode = Slow()

    def run(self) -> str:
        return self.mode.go()


class HttpTransport:
    def send(self) -> str:
        return "http"


class FakeTransport:
    def send(self) -> str:
        return "fake"


class LocalTransport:
    def send(self) -> str:
        return "local"


class DiskBackup:
    def save(self) -> str:
        return "disk"


class TapeBackup:
    def save(self) -> str:
        return "tape"


def default_transport() -> HttpTransport:
    return HttpTransport()


class Client:
    def __init__(self, transport: object = None) -> None:
        self.transport = transport or default_transport()
        self.backup = DiskBackup()

    def use_fake(self) -> None:
        self.transport = FakeTransport()

    def post(self) -> str:
        return self.transport.send() + self.backup.save()


class OfflineClient(Client):
    def __init__(self) -> None:
        super().__init__()
        self.transport = LocalTransport()


class RedisCache:
    def get(self) -> str:
        return "redis"


class NullCache:
    def get(self) -> str:
        return ""


class Store:
    def __init__(self, enabled: bool) -> None:
        self.cache: RedisCache = NullCache() if not enabled else RedisCache()  # type: ignore

    def lookup(self) -> str:
        return self.cache.get()


def forgotten() -> None:
    pass


if __name__ == "__main__":
    switcher = Switcher()
    switcher.reset()
    client = OfflineClient() if sys.argv[1:] else Client()
    client.backup = TapeBackup()
    print(Layout(wide=False).run(), switcher.run(), client.post(), Store(False).lookup())
