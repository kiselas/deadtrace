from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import FromDishka, inject, setup_dishka
from fastapi import FastAPI


class Service:
    pass


class ComponentProvider(Provider):
    component = "billing"

    @provide(scope=Scope.REQUEST)
    def service(self) -> Service:
        return Service()


app = FastAPI()


@app.get("/")
@inject
def endpoint(service: FromDishka[Service]) -> None:
    del service


container = make_async_container(ComponentProvider())
setup_dishka(container, app)
