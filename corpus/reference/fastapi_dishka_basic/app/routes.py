from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter

from .domain import Service

router = APIRouter()


@router.get("/dish")
@inject
async def get_dish(service: FromDishka[Service]) -> dict[str, str]:
    return {"dish": service.get()}
