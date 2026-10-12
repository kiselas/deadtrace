from fastapi import APIRouter

from shop.routes.admin import users

router = APIRouter(prefix="/admin")
router.include_router(users.router)
