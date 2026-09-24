# FastAPI factory run by the server

`main.create_app` builds a FastAPI application and includes a router, and
`uvicorn main:create_app --factory` calls it; no project module does. The factory is the
application of the automatic `production:web` world, so the route `list_items` and what it
calls are live through the FastAPI model rather than guarded. `unused_endpoint_helper` stays
a candidate.
