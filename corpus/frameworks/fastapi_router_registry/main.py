from fastapi import FastAPI
from helpers import apply_routers

app = FastAPI()
apply_routers(app)


def unused() -> None:
    pass
