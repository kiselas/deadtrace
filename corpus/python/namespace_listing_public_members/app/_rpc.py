import inspect


class Service:
    def ping(self):
        return "pong"

    def _internal(self):
        return "only the class calls private helpers"


def rpc_methods(obj):
    return [
        (name, method)
        for name, method in inspect.getmembers(obj, inspect.ismethod)
        if not name.startswith("_")
    ]
