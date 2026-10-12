import sys

from app._datasets import Datasets


def main():
    print(Datasets.load(sys.argv[1], [1, 2]))


if __name__ == "__main__":
    main()
