from dependency_injector import containers, providers


class Gateways(containers.DeclarativeContainer):
    mikrotik = providers.Singleton(object)


class Service:
    def __init__(self, gateways: Gateways) -> None:
        self.client = gateways.mikrotik()


if __name__ == "__main__":
    Service(Gateways())
