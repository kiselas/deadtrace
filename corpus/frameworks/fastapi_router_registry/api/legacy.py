from fastapi import APIRouter

router = APIRouter()


@router.get("/legacy")
def legacy() -> list[str]:
    return []
