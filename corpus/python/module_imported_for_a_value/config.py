def load() -> dict[str, str]:
    return {"mode": "production"}


settings = load()


def unused_loader() -> None:
    pass
