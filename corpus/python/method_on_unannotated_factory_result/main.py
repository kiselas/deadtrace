class Repository:
    def fetch(self) -> int:
        return 1


def make_repository():
    return Repository()


def unused_control() -> str:
    return "never called"


def main() -> None:
    repository = make_repository()
    print(repository.fetch())
