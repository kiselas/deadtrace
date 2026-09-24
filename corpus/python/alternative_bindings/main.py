import sys

try:
    from fast import speedup
except ImportError:
    from slow import speedup

if sys.platform == "win32":

    def clear_screen() -> None:
        print("cls")

else:

    def clear_screen() -> None:
        print("clear")


def main() -> None:
    speedup()
    clear_screen()
