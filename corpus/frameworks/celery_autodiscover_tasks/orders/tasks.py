from celery import shared_task

from orders.receipts import render_receipt


@shared_task
def send_receipt(order_id: int) -> str:
    return render_receipt(order_id)
