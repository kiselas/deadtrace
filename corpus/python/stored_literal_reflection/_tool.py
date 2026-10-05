class Worker:
    def run(self):
        return 1

    def idle(self):
        return 0


def main():
    worker = Worker()
    callback = getattr(worker, "run")  # noqa: B009 - intentional reflected-value case
    callback()
