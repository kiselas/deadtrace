from fastapi import FastAPI


class Wrapper:
    def __init__(self, api: FastAPI) -> None:
        self.api = api


def create_application() -> Wrapper:
    api = FastAPI()

    @api.get("/")
    def index() -> str:
        return "ok"

    return Wrapper(api)


def create_default() -> Wrapper:
    return create_application()


def unused() -> None:
    pass
