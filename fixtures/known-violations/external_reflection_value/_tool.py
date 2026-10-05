from pathlib import Path


class ProjectPath(Path):
    def check(self):
        return True


def _unused_control():
    return False


def main(path: Path, name):
    callback = getattr(path, name)
    callback()
