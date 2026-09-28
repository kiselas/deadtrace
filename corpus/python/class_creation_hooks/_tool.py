import _plugins
from _registry import REGISTRY, Registered


def register_local() -> None:
    class Local(Registered):
        pass


if __name__ == "__main__":
    register_local()
    print(_plugins, REGISTRY)
