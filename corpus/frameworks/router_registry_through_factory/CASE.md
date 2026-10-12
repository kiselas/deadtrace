# Routers mounted through a registry by an application factory

`create_app` imports `register_routes` inside its body, so the call that passes the application
cannot be resolved, and `register_routes` mounts `ROUTERS` (`orders.router`, `admin.router`) in a loop
and `reports_router`, imported inside the function, and `billing_routes.router` of a module imported
inside the function under another name. Each of those routers may be published, and
so is `users.router`, which `admin.router` includes. None of their routes is reported. `legacy.router`
is referred to nowhere: its route stays an RCH002 finding.
