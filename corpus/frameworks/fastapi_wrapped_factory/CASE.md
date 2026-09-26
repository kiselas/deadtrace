# FastAPI application returned inside a wrapper

A factory builds the FastAPI application and returns it inside a wrapper, such as an ASGI
middleware or a dataclass with services. A server runs another function by name, as
`uvicorn app.main:create_default --factory` does, and nothing in the project calls it.

The factory is an application factory although it does not return the application itself, and
the uncalled function that calls it is a root of the application's world. The unsafe outcome is
reporting `create_default` as unreached; the useless one is treating the project as a library,
so that nothing is reported. A function nothing calls is still reported.
