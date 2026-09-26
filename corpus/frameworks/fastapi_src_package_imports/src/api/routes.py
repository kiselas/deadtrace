from fastapi import APIRouter

router = APIRouter(prefix="/items")


@router.get("/")
def list_items() -> list[str]:
    return []


def unused_helper() -> None:
    pass
