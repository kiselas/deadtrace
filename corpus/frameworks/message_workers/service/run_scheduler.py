from taskiq import InMemoryBroker, TaskiqEvents, TaskiqScheduler, TaskiqState

broker = InMemoryBroker()


@broker.on_event(TaskiqEvents.CLIENT_STARTUP)
async def setup(state: TaskiqState) -> None:
    pass


scheduler = TaskiqScheduler(broker=broker, sources=[])
