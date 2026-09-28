from fastapi import FastAPI

from billing.api import helper

app = FastAPI()


@app.get("/")
def root() -> int:
    return helper()
