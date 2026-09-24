def normalize(value: str) -> str:
    return value.strip().lower()


class LegacyService:
    def run(self, value: str) -> str:
        return normalize(value)


def endpoint(value: str) -> str:
    return normalize(value)
