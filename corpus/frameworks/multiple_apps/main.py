from fastapi import FastAPI

first = FastAPI()
second = FastAPI()


@first.get("/first")
def first_endpoint() -> None:
    pass


@second.get("/second")
def second_endpoint() -> None:
    pass
