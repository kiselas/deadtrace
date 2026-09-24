from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import FromDishka, inject, setup_dishka
from fastapi import FastAPI


class Service:
    pass


class FirstProvider(Provider):
    @provide(scope=Scope.REQUEST)
    def service(self) -> Service:
        return Service()


class SecondProvider(Provider):
    @provide(scope=Scope.REQUEST)
    def service(self) -> Service:
        return Service()


first = FastAPI()
second = FastAPI()


@first.get("/first")
@inject
def first_endpoint(service: FromDishka[Service]) -> None:
    del service


@second.get("/second")
@inject
def second_endpoint(service: FromDishka[Service]) -> None:
    del service


first_container = make_async_container(FirstProvider())
second_container = make_async_container(SecondProvider())
setup_dishka(first_container, first)
setup_dishka(second_container, second)
