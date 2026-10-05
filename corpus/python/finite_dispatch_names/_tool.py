class First:
    def run(self):
        return 1

    def other(self):
        return 2

    def unused(self):
        return 3


class Second:
    def run(self):
        return 1

    def other(self):
        return 2


def main(flag, unknown):
    item = First()
    name = "run" if flag else "other"
    alias = name
    name = unknown
    getattr(item, alias)()
    second = Second()
    method = "run"
    if flag:
        method = unknown
    getattr(second, method)()
