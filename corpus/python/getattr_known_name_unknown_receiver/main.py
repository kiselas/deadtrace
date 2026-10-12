import sys

from app._llm import Llm


def run(llm, kind):
    getattr(llm, "saveState")("model")
    return getattr(llm, f"load_{kind}")()


def main():
    print(run(Llm(), sys.argv[1]))


if __name__ == "__main__":
    main()
