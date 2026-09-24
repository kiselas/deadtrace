__all__ = ["slugify"]
__all__ += ["_legacy_slugify"]


def slugify(text: str) -> str:
    return text.lower()


def normalize(text: str) -> str:
    return text.strip()


def _legacy_slugify(text: str) -> str:
    return slugify(text)


def _unlisted() -> None:
    pass
