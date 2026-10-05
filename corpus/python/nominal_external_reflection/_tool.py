from pathlib import Path

from external import Bridge


class ProjectPath(Path):
    def check(self):
        return True


class OpaquePath(Bridge):
    def check(self):
        return True


class Unrelated:
    def idle(self):
        return False


def main(path: Path, name):
    getattr(path, name)()
