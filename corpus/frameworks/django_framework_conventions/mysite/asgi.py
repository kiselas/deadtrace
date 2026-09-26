from django.core.asgi import get_asgi_application
from shop.routing import websocket_urlpatterns

application = get_asgi_application()
routes = websocket_urlpatterns
