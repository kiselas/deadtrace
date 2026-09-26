from fastapi import FastAPI
from registry import discover

app = FastAPI()
for router in discover():
    app.include_router(router)
