from typing import cast


class ArchiveStrategy:
    def _build(self):
        return "tar"

    def _unused(self):
        return None


class Artifact:
    def __init__(self, archive):
        self.archive = archive

    def build(self):
        return cast(ArchiveStrategy, self.archive)._build()

    def build_quoted(self):
        return cast("ArchiveStrategy", self.archive)._build()
