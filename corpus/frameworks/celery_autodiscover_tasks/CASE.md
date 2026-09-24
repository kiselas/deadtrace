# Celery task autodiscovery

`proj.celery` creates the Celery application and calls `app.autodiscover_tasks()`,
which imports a `tasks` module from each application package. Nothing imports
`orders.tasks` by name, yet its `@shared_task` function runs in the worker. The
application module is the root of the automatic `production:celery` world and may import
any module named `tasks`, which protects `send_receipt` and what it calls.
`orders.legacy_tasks` is not named `tasks`, so its task and `unused_template` stay
candidates.
