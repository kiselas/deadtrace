INSTALLED_APPS = ["django.contrib.contenttypes", "shop"]
MIGRATION_MODULES = {"shop": "shop.legacy_migrations"}
REALTIME = False
if REALTIME:
    ASGI_APPLICATION = "mysite.asgi.application"
