class Trace:
    def setwriter(self, writer):
        self._writer = writer

    def _unused(self):
        return 0


class Wrapper:
    def __init__(self, root: Trace):
        self.root = root
