import pickle
import sys


def execute(job) -> str:
    return job.run()


def forgotten() -> None:
    pass


if __name__ == "__main__":
    print(execute(pickle.loads(sys.stdin.buffer.read())))
