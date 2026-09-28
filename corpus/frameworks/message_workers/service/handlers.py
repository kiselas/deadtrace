from faststream.rabbit import RabbitRouter

router = RabbitRouter()


@router.subscriber("orders")
async def handle(message: str) -> None:
    pass


def forgotten() -> None:
    pass
