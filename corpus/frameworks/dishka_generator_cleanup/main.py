from collections.abc import Iterator

from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import FromDishka, inject, setup_dishka
from fastapi import FastAPI


class Resource:
    pass


def cleanup(resource: Resource) -> None:
    del resource


class AppProvider(Provider):
    @provide(scope=Scope.REQUEST)
    def resource(self) -> Iterator[Resource]:
        resource = Resource()
        yield resource
        cleanup(resource)


app = FastAPI()


@app.get("/")
@inject
def endpoint(resource: FromDishka[Resource]) -> None:
    del resource


container = make_async_container(AppProvider())
setup_dishka(container, app)
