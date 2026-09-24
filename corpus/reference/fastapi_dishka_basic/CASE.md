# FastAPI + Dishka reference application

`main.app` includes `routes.router`, activates Dishka, and binds a request-scoped service to a
repository. Calling `GET /dish` must execute the endpoint, service provider, repository provider,
service method, and repository method. The registered legacy provider must not be requested.

`normalize` is shared by live and legacy code and must remain live. The expected analyzer output is
one RCH003 review group for the unrequested legacy binding; it is not permission to delete it.

The oracle test imports this trusted fixture only inside the separate oracle suite and verifies
actual routes and provider events. Static scanner tests verify that ordinary analysis does not
execute the canary in `app/__init__.py`.
