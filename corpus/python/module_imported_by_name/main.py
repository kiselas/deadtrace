import importlib


def unused_control() -> str:
    return "never called"


def load(name: str) -> None:
    importlib.import_module(f"plugins.{name}")


def main() -> None:
    importlib.import_module("plugins.alpha")
    load("beta")
