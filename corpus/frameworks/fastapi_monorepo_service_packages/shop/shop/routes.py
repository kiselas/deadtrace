from fastapi import APIRouter

router = APIRouter()


@router.get("/items")
def items() -> list[str]:
    return []


def forgotten() -> None:
    pass
