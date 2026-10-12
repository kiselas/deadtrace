import sys

from app._plugins import Plugin


def dispatch(obj, name):
    return getattr(obj, name)()


def main():
    print(dispatch(Plugin(), sys.argv[1]))


if __name__ == "__main__":
    main()
