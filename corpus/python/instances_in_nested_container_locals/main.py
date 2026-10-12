import sys

from app._download import download


def main():
    print(download(sys.argv[1], sys.argv[2]))


if __name__ == "__main__":
    main()
