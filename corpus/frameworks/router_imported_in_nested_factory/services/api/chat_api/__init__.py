import fastapi


def create_app() -> fastapi.FastAPI:
    app = fastapi.FastAPI()

    from chat_api.routes import messages

    app.include_router(messages.router)
    return app
