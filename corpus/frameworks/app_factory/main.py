from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import FromDishka, inject, setup_dishka
from fastapi import APIRouter, FastAPI


class Service:
    pass


class AppProvider(Provider):
    @provide(scope=Scope.REQUEST)
    def service(self) -> Service:
        return Service()


router = APIRouter()


@router.get("/")
@inject
def endpoint(service: FromDishka[Service]) -> None:
    del service


container = make_async_container(AppProvider())


def create_app() -> FastAPI:
    application = FastAPI()
    application.include_router(router)
    setup_dishka(container, application)
    return application


app = create_app()
