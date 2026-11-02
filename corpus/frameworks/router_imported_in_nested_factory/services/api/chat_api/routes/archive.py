import fastapi

router = fastapi.APIRouter()


@router.get("/archive")
def archived_messages() -> list[str]:
    return []
