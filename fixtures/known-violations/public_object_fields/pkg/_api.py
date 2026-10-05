from ._objects import Trace, Wrapper


class Manager:
    def __init__(self):
        self.trace: Wrapper = Wrapper(Trace())
