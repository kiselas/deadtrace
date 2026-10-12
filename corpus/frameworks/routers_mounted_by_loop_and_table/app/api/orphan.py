from fastapi import APIRouter

router = APIRouter()


@router.get("/orphan")
def list_orphan():
    return []
