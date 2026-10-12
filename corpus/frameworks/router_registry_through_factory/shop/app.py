from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI()
    from shop.routes import register_routes

    register_routes(app)
    return app
