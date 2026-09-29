def workers() -> int:
    try:
        from os import sched_getaffinity

        def cpu_count():
            return len(sched_getaffinity(0))

    except ImportError:
        try:
            from os import cpu_count
        except ImportError:
            from multiprocessing import cpu_count
    return cpu_count()


def unused() -> None:
    pass


if __name__ == "__main__":
    print(workers())
