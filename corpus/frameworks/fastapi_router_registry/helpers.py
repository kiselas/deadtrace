from api import protected_routers, public_routers
from fastapi import Depends, FastAPI


def current_user() -> str:
    return "user"


def apply_routers(app: FastAPI) -> None:
    for router in public_routers:
        app.include_router(router, prefix="/v1")
    for router in protected_routers:
        app.include_router(router, prefix="/v1", dependencies=[Depends(current_user)])
