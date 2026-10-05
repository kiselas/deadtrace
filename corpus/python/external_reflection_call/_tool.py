from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


class ProjectPath(Path):
    def check(self):
        return True

    def arbitrary(self):
        return False


def _unused_control():
    return False


def main(path: "Path", unknown):
    names = {"check": 1}
    names[unknown] = 2
    alias = path
    for name in names:
        getattr(alias, name)()
