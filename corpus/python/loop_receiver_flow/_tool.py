class First:
    def run(self):
        return 1


class Second:
    def run(self):
        return 2


def main(items):
    item = First()
    for _value in items:
        item.run()
        item = Second()


if __name__ == "__main__":
    main([1, 2])


def _unused_control():
    return 0
