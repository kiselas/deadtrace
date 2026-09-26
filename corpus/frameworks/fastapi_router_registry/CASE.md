# Routers included by a helper from literal lists

Services often keep their routers in lists in `api/__init__.py` and include them from a helper
that receives the application: `apply_routers(app)` loops over `public_routers` and
`protected_routers` and calls `app.include_router(router, ...)`. Every listed router is published,
its routes run, and the dependencies given to `include_router` run for each of them.

The unsafe outcome is reporting the listed routers as unpublished (`RCH002`) or their include
dependencies as unreached. A router that no list names and nothing includes is still reported,
so the case cannot pass by suppressing the finding altogether.
