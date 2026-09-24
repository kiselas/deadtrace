from celery import Celery

app = Celery("jobs")


@app.task
def send_email(address: str) -> None:
    print(address)


def main() -> None:
    send_email.delay("user@example.com")
