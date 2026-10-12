from somelib import register

from app._handlers import Handler


def main():
    register(Handler)


if __name__ == "__main__":
    main()
