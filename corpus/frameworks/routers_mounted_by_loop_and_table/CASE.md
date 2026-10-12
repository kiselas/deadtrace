# Routers mounted in a loop and from a table of module names

`app/main.py` mounts the routers of `users` and `items` with
`for module in (users, items): app.include_router(module.router)`, and the router of `app.api.plugin`
from a table of `(module name, attribute)` pairs through `import_module` and `getattr`. Those routes
are served. `orphan.router` is mounted nowhere: its route is a candidate.
