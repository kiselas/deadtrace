import importlib
from types import ModuleType

import _plugins._shop
import _shop


def load_tables(obj: object) -> None:
    importlib.import_module(f"{obj.__module__}.tables")


def load_plugin_tables(package: ModuleType) -> None:
    importlib.import_module(f"{package.__name__}.tables")


if __name__ == "__main__":
    load_tables(_shop.Order())
    load_plugin_tables(_plugins._shop)
