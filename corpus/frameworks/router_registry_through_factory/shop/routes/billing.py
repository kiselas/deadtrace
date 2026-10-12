from fastapi import APIRouter

router = APIRouter()


@router.get("/billing")
def list_invoices() -> list[int]:
    return []
