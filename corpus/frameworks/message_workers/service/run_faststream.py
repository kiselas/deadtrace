from faststream import FastStream
from faststream.rabbit import RabbitBroker

from service.handlers import router

broker = RabbitBroker()
broker.include_router(router)
app = FastStream(broker)
