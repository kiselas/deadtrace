from fastapi import FastAPI
from report.api import router

app = FastAPI()
app.include_router(router)
