def callback_helper(value: str) -> str:
    return value.upper()


def callback(value: str) -> str:
    return callback_helper(value)


def register_external(handler: object) -> None:
    del handler


register_external(callback)
