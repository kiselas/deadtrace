REGISTRY: list[type] = []


class Registered:
    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        REGISTRY.append(cls)
