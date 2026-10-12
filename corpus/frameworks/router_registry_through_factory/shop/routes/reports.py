from fastapi import APIRouter

reports_router = APIRouter()


@reports_router.get("/reports")
def list_reports() -> list[int]:
    return []
