import subprocess
import sys


def unused() -> str:
    return "never called"


def main() -> None:
    subprocess.run([sys.executable, "_worker.py"], check=True)


if __name__ == "__main__":
    main()
