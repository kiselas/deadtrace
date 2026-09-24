class Settings:
    debug: bool = False


def configure(settings: Settings) -> bool:
    return settings is None


def unused_control() -> str:
    return "never called"


def main() -> None:
    print(configure(None))
