class First:
    def run(self):
        return 1


class Second:
    def run(self):
        return 2


def main(flag):
    if flag:  # noqa: SIM108 -- preserve the control-flow merge under test
        item = First()
    else:
        item = Second()
    return item.run()


if __name__ == "__main__":
    main(True)
    main(False)


def _unused_control():
    return 0
