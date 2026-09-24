from dishka import Provider, Scope, from_context, make_async_container, provide
from dishka.integrations.fastapi import FastapiProvider, FromDishka, inject, setup_dishka
from fastapi import FastAPI, Request


class Config:
    pass


class Service:
    def __init__(self, request: Request, config: Config) -> None:
        self.request = request
        self.config = config


class AppProvider(Provider):
    request = from_context(provides=Request, scope=Scope.REQUEST)
    config = from_context(provides=Config, scope=Scope.APP, override=True)

    @provide(scope=Scope.REQUEST)
    def service(self, request: Request, config: Config) -> Service:
        return Service(request, config)


app = FastAPI()


@app.get("/")
@inject
def endpoint(service: FromDishka[Service]) -> None:
    del service


config = Config()
container = make_async_container(AppProvider(), FastapiProvider(), context={Config: config})
setup_dishka(container, app)
