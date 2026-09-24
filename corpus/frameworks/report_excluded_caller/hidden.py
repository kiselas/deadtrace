from fastapi import FastAPI
from visible import visible_helper

app = FastAPI()


@app.get("/hidden")
async def hidden_endpoint() -> dict[str, str]:
    return {"value": visible_helper()}
