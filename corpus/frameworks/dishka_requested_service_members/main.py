from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import FromDishka, inject, setup_dishka
from fastapi import FastAPI


class Ledger:
    def write(self) -> None:
        pass

    def purge(self) -> None:
        pass


class Service:
    def __init__(self, ledger: Ledger) -> None:
        self.ledger = ledger

    def charge(self) -> None:
        self.ledger.write()

    def retired(self) -> None:
        pass


class AppProvider(Provider):
    ledger = provide(Ledger, scope=Scope.REQUEST)
    service = provide(Service, scope=Scope.REQUEST)


app = FastAPI()


@app.get("/")
@inject
def endpoint(service: FromDishka[Service]) -> None:
    service.charge()


container = make_async_container(AppProvider())
setup_dishka(container, app)
