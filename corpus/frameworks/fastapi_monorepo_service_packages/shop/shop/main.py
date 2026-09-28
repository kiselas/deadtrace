from fastapi import FastAPI

from shop.routes import router

app = FastAPI()
app.include_router(router)
