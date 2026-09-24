class Document:
    def render(self) -> str:
        return self._body()

    def _body(self) -> str:
        return ""

    def _unused_private(self) -> None:
        pass
