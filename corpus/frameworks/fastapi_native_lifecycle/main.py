from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import BackgroundTasks, Depends, FastAPI
from pydantic import BaseModel, field_validator


def token() -> str:
    return "token"


def auth(value: Annotated[str, Depends(token)]) -> None:
    del value


def cleanup_helper() -> None:
    pass


def background_job() -> None:
    pass


def validation_helper() -> None:
    pass


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    del app
    yield
    cleanup_helper()


class Payload(BaseModel):
    value: str

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: str) -> str:
        del cls
        validation_helper()
        return value


app = FastAPI(lifespan=lifespan)


@app.post("/", dependencies=[Depends(auth)])
def endpoint(payload: Payload, tasks: BackgroundTasks) -> Payload:
    tasks.add_task(background_job)
    return payload
