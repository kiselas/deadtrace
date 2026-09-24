from celery import Celery

app = Celery("jobs")


@app.task
def nightly_cleanup() -> None:
    """Scheduled by the beat configuration; never referenced from Python code."""


def main() -> None:
    app.start()
