from app._handlers import Handler
from somelib import register


def main():
    register(Handler)


if __name__ == "__main__":
    main()
