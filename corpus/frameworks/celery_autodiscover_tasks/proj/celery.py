from celery import Celery

app = Celery("proj")
app.autodiscover_tasks()
