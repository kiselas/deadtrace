class Walker:
    def descendants(self, flag: bool, deep: bool) -> int:
        if flag:

            def fn(rev):
                return rev + 1

        elif deep:

            def fn(rev):
                return rev + 2

        else:

            def fn(rev):
                return rev + 3

        return self.iterate(fn, 1)

    def iterate(self, fn, start):
        return fn(start)

    def unused(self) -> None:
        pass


if __name__ == "__main__":
    print(Walker().descendants(True, False))
