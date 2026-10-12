import inspect


class Context:
    def calculate(self, op):
        func_name = "_On" + op
        handler = type(self).__dict__.get(func_name)
        return handler(self) if handler else None

    def _OnConstant(self):
        return 1

    def _helper(self):
        return 2


class Service:
    def ping(self):
        return "pong"


def describe(obj):
    return [name for name, value in inspect.getmembers(obj) if inspect.ismethod(value)]


def _unused():
    return None
