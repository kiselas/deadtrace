def handle_create() -> str:
    return "created"


def handle_delete() -> str:
    return "deleted"


HANDLERS = {"create": handle_create, "delete": handle_delete}


def dispatch(action: str) -> str:
    return HANDLERS[action]()


def unused_control() -> str:
    return "never called"


def main() -> None:
    print(dispatch("create"))
