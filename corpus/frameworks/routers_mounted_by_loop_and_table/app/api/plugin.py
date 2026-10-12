from fastapi import APIRouter

router = APIRouter()


@router.get("/plugin")
def list_plugin():
    return []
