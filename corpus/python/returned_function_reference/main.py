def compute() -> int:
    return 42


def select_operation():
    return compute


def unused_control() -> str:
    return "never called"


def main() -> None:
    operation = select_operation()
    print(operation())
