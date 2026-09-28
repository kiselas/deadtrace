from fastapi import APIRouter

router = APIRouter()


@router.get("/summary")
def summary() -> str:
    return "ok"
