from celery import shared_task


@shared_task
def resend_all() -> None:
    pass
