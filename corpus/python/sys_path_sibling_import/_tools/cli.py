import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import console  # noqa: E402


def main() -> None:
    print(console.colour("ok"))


if __name__ == "__main__":
    main()
