class Filter:
    def __init__(self) -> None:
        self._label = ""

    def label():
        def fget(self):
            return self._label

        def fset(self, value):
            self._label = value

        return locals()

    label = property(**label())

    def unused(self) -> None:
        pass


if __name__ == "__main__":
    item = Filter()
    item.label = "name"
    print(item.label)
