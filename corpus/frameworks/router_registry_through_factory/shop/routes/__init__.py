from fastapi import FastAPI

from shop.routes import admin, orders

ROUTERS = (orders.router, admin.router)


def register_routes(app: FastAPI) -> None:
    for router in ROUTERS:
        app.include_router(router)
    from shop.routes.reports import reports_router

    app.include_router(reports_router)
    from shop.routes import billing as billing_routes

    app.include_router(billing_routes.router)
