import os

from django.core.wsgi import get_wsgi_application


def configure_monitoring() -> None:
    pass


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")
configure_monitoring()
application = get_wsgi_application()
