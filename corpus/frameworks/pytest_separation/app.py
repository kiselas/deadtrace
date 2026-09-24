from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def endpoint() -> str:
    return "live"


def test_only_helper() -> str:
    return "fixture"


def unused() -> None:
    pass
