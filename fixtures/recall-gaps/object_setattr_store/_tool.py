class Stored:
    def __init__(self):
        object.__setattr__(self, "value", 1)

    def read(self):
        return self.value

    def idle(self):
        return 0


def main():
    return Stored().read()
