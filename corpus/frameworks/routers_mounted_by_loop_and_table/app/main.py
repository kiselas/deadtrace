import importlib

from fastapi import FastAPI

from app.api import items, users

_PLUGINS = [("app.api.plugin", "router")]

app = FastAPI()
for module in (users, items):
    app.include_router(module.router, prefix="/api")
for path, attr in _PLUGINS:
    app.include_router(getattr(importlib.import_module(path), attr))
