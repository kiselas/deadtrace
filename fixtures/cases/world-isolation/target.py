class ProductionGateway:
    def send(self) -> None:
        pass


class TestGateway:
    def send(self) -> None:
        pass


def production_entry(gateway: ProductionGateway) -> None:
    gateway.send()


def test_entry(gateway: TestGateway) -> None:
    gateway.send()
