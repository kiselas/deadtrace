from .adapters import _claude, _codex

LOADERS = {"claude": _claude, "codex": _codex}


def run(name, cutoff=0):
    loader = LOADERS.get(name)
    if loader is None:
        return []
    recent = getattr(loader, "load_recent", None)
    return recent(cutoff) if recent else loader.load_entries()
