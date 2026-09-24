from fastapi import APIRouter, FastAPI

app = FastAPI()
hidden = APIRouter()


@app.get("/")
def live_endpoint() -> None:
    pass


@hidden.get("/hidden")
def hidden_endpoint() -> None:
    pass
