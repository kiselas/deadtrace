from __future__ import annotations

EVENTS: list[str] = []


def normalize(value: str) -> str:
    return value.strip().lower()


class Repository:
    def load(self) -> str:
        EVENTS.append("repository.load")
        return "  BORSCH  "


class Service:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def get(self) -> str:
        EVENTS.append("service.get")
        return normalize(self.repository.load())


class LegacyService:
    def run(self) -> str:
        EVENTS.append("legacy.run")
        return normalize("legacy")
