from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import FromDishka, setup_dishka
from fastapi import FastAPI


class Service:
    pass


class AppProvider(Provider):
    @provide(scope=Scope.REQUEST)
    def service(self) -> Service:
        return Service()


app = FastAPI()


@app.get("/")
def endpoint(service: FromDishka[Service]) -> None:
    del service


container = make_async_container(AppProvider())
setup_dishka(container, app)
