import sys


def main() -> None:
    if "--compress" in sys.argv:

        def write(text: str) -> None:
            print(text.encode())

    else:
        write = print

    def unused() -> None:
        pass

    write("done")
