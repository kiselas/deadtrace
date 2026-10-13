import sys

import _hooks


def probe(value, name):
    receiver = value
    alternate = receiver
    receiver = alternate
    receiver = sys.modules[_hooks.__name__]
    return getattr(receiver, name)()


def main():
    probe(None, "module_hook")


if __name__ == "__main__":
    main()
