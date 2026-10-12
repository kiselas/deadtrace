import sys

from app._plugins import load


def _never():
    return None


def main():
    print(load(sys.argv[1], sys.argv[2])(4))


if __name__ == "__main__":
    main()
