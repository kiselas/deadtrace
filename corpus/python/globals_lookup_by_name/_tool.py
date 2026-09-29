def _render_ARRAY_type(value: object) -> str:
    return "array"


def _render_JSON_type(value: object) -> str:
    return "json"


def _render_other(value: object) -> str:
    return "other"


def _named(value: object) -> str:
    return "named"


def render(kind: str, value: object) -> str:
    if "_render_%s_type" % kind in globals():  # noqa: UP031
        fn = globals()["_render_%s_type" % kind]  # noqa: UP031
        return fn(value)
    return globals().get("_named")(value)


if __name__ == "__main__":
    print(render("ARRAY", 1))
