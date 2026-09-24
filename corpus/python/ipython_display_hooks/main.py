class Table:
    def _repr_html_(self) -> str:
        return "<table></table>"

    def _repr_mimebundle_(self, include: object = None, exclude: object = None) -> dict:
        return {"text/plain": "table"}

    def _render(self) -> str:
        return ""


def main() -> Table:
    return Table()
