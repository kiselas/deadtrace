import functools


def log_calls(function):
    @functools.wraps(function)
    def wrapper(*args, **kwargs):
        return function(*args, **kwargs)

    return wrapper


@log_calls
def decorated() -> int:
    return 1


def unused_control() -> str:
    return "never called"


def main() -> None:
    print(decorated())
