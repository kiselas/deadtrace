# Services of a monorepo that each hold a package of their name

A monorepo keeps each service in a directory without `__init__.py` that holds a package of the
same name, and each service runs with its own directory as the working directory, which Python
puts on `sys.path`:

- `shop/shop/main.py` runs `from shop.routes import router`, so `shop` names `shop/shop` rather
  than the directory `shop/` at the root, and includes the router.
- `billing/billing/main.py` calls `helper` from `billing.api`, which calls `round_down` of the
  library `libs/common/common`; the services install it in editable mode and import it as
  `common`, and it has no `__init__.py` either.
- The package of the `report` service has no `__init__.py`, a namespace portion that merges
  with the other portions of its name. The service keeps Alembic migrations in
  `report/report/alembic/`, whose `env.py` imports the installed `alembic`, not that directory.

The unsafe outcome is resolving these imports against the root, where the names do not exist,
and reporting the included router (`RCH002`), a handler of the namespace service, a helper or
library function a service calls, or the service's migrations. Code that nothing uses in a
service or the library is still reported.
