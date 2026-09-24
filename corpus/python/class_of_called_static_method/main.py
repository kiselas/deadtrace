class Tools:
    @staticmethod
    def helper() -> int:
        return 2


def unused_control() -> str:
    return "never called"


def main() -> None:
    print(Tools.helper())
