from dishka import Provider, Scope, alias, make_async_container, provide
from dishka.integrations.fastapi import FromDishka, inject, setup_dishka
from fastapi import FastAPI


class Repository:
    pass


class SqlRepository(Repository):
    pass


class Service:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository


class AppProvider(Provider):
    repository = provide(SqlRepository, scope=Scope.REQUEST)
    repository_alias = alias(source=SqlRepository, provides=Repository)
    service = provide(Service, scope=Scope.REQUEST)


app = FastAPI()


@app.get("/")
@inject
def endpoint(service: FromDishka[Service]) -> None:
    del service


container = make_async_container(AppProvider())
setup_dishka(container, app)
