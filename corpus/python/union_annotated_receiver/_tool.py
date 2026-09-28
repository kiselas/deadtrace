class Plain:
    def status(self) -> str:
        return "plain"


class Slug:
    def status(self) -> str:
        return "slug"


class Builder:
    def __init__(self, proxy: Plain | Slug) -> None:
        self.proxy = proxy

    def build(self) -> str:
        return self.proxy.status()


def forgotten() -> None:
    pass


if __name__ == "__main__":
    print(Builder(Slug()).build(), Plain())
