import warnings


def create() -> type:
    class Validator:
        def __init_subclass__(cls) -> None:
            warnings.warn("subclassing is deprecated", DeprecationWarning, stacklevel=2)

    return Validator


Draft7 = create()
