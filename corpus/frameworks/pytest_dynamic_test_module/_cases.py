class Suite:
    def cases(self) -> list[str]:
        return ["a", "b"]

    def to_testcase(self, cases: list[str], skip=None) -> type:
        return type("Generated", (), {name: skip for name in cases})

    def unused(self) -> None:
        pass


def make() -> Suite:
    return Suite()
