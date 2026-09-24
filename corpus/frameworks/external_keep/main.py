from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def endpoint() -> None:
    pass


def hook_helper() -> None:
    pass


def external_hook() -> None:
    hook_helper()


def unused() -> None:
    pass
