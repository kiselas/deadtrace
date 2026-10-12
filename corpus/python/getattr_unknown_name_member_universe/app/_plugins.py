class Plugin:
    def handle(self):
        return "handled"

    def _audit(self):
        return "audited"


def helper():
    return "never called"
