from typing import Generic, TypeVar

T = TypeVar("T")


class BaseRepo(Generic[T]):  # noqa: UP046
    def get(self):
        return self._load()

    def _load(self):
        raise NotImplementedError

    def _base_only_unused(self):
        return None
