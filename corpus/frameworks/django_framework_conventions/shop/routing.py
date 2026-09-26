from shop.consumers import LiveConsumer

websocket_urlpatterns = [LiveConsumer.as_asgi()]
