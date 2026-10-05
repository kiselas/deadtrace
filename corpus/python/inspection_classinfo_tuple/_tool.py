from external import consume


class Checked:
    def idle(self):
        return 0


class Escaped:
    def run(self):
        return 1


def main(value):
    consume((Escaped,))
    return isinstance(value, (Checked, (int, str)))
