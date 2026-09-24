from dishka import make_async_container
from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI

from .providers import AppProvider
from .routes import router

app = FastAPI()
app.include_router(router)

container = make_async_container(AppProvider())
setup_dishka(container=container, app=app)
