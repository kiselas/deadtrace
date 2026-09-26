# Router included by an unresolved `include_router` call

The application includes whatever routers a function returns: `for router in discover():
app.include_router(router)`. The routers it may include are not known statically, but only a
router that code refers to can reach that call. `listed` is imported by the registry, so it may
be published and must not be reported as unpublished.

`hidden` is used only to decorate its route; no include can receive it, so it is still reported
as `RCH002`. The unsafe outcome is reporting `listed`; the useless one is reporting neither.
