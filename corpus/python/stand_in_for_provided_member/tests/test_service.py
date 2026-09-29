from _service import Service


class _GatewaysStub:
    def mikrotik(self) -> object:
        return object()

    def other(self) -> object:
        return object()


def test_service() -> None:
    Service(gateways=_GatewaysStub())
