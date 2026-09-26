from fastapi import APIRouter

listed = APIRouter()
hidden = APIRouter()


@listed.get("/listed")
def listed_endpoint() -> str:
    return "listed"


@hidden.get("/hidden")
def hidden_endpoint() -> str:
    return "hidden"
