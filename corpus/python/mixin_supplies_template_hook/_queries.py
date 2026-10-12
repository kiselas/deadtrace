class BaseQuery:
    def run(self) -> list[str]:
        return self._filter([])

    def _filter(self, rows: list[str]) -> list[str]:
        raise NotImplementedError


class _NoFilterMixin:
    def _filter(self, rows: list[str]) -> list[str]:
        return rows


class _UnusedMixin:
    def _filter(self, rows: list[str]) -> list[str]:
        return []


class SortQuery(_NoFilterMixin, BaseQuery):
    pass


def main() -> None:
    print(SortQuery().run())


if __name__ == "__main__":
    main()
