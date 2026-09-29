class Commands:
    def commit(self) -> str:
        return self._build_header("x") + self.provided_elsewhere()


class Extra:
    def provided_elsewhere(self) -> str:
        return "extra"


class Graph(Commands, Extra):
    def _build_header(self, value: str) -> str:
        return "H " + value

    def unused(self) -> None:
        pass


class Stranger:
    def provided_elsewhere(self) -> str:
        return "no"

    def _build_header(self, value: str) -> str:
        return value


if __name__ == "__main__":
    print(Graph().commit())
