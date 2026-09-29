from pkg._api import Process


class Impl(Process):
    def terminate(self) -> None:
        pass

    def kill(self) -> None:
        pass

    def helper(self) -> None:
        pass


class _Dead(Process):
    def terminate(self) -> None:
        pass

    def kill(self) -> None:
        pass
