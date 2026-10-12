import sys

from app._graph import Context, Service, describe


def main():
    print(Context().calculate(sys.argv[1]), describe(Service()))


if __name__ == "__main__":
    main()
