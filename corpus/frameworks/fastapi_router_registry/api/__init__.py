from .items import router as items_router
from .users import router as users_router

public_routers = [items_router]
protected_routers = [users_router]
