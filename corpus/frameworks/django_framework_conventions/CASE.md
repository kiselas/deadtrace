# Django conventions outside settings

Django instantiates the `AppConfig` subclass of an installed application's `apps` module and
calls its `ready()`. Model and serializer metaclasses read nested `Meta` classes. An application
server loads `asgi.py`, which builds the application and imports the WebSocket routing, whether
or not `ASGI_APPLICATION` is assigned in a branch that runs. `MIGRATION_MODULES` moves an
application's migrations to another package, whose `RunPython` callbacks are historical
contracts like those of a `migrations` package.

The unsafe outcome is reporting `ready`, `Product.Meta`, the routing consumer, or the relocated
migration callback as unreached. A module that nothing imports is still reported.
