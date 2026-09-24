from fastapi import APIRouter

router = APIRouter()


@router.get("/items")
def list_items() -> list[str]:
    return load_items()


def load_items() -> list[str]:
    return []


def unused_endpoint_helper() -> None:
    pass
