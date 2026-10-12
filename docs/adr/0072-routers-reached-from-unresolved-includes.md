# ADR-0072: Routers reached from an unresolved include are not reported

**Status:** Accepted, 2026-10-12; model revision 54.

RCH002 reports routes on a router that no discovered application includes. An `include_router` call
whose application or router cannot be resolved makes every *escaping* router (one that code refers
to other than through its own route decorators) possibly published (ADR-0017). In the blind cohort
of model 53, 16 of 17 reviewed RCH002 findings were false, for three reasons this rule missed:

- a possibly published router includes other routers (`admin.router.include_router(users.router)`),
  and only applications were followed through includes;
- a router read as a module attribute (`ROUTERS = (orders.router, ...)` after `from pkg import
  orders`) was not counted as escaping;
- a router imported inside the function that assembles the routes (`from pkg.routers.auth import
  auth_router` in `build_v1_router`) was not counted as escaping, since only top-level imports were.

Now the routers that possibly published routers include are possibly published too, transitively;
an attribute read `module.router` of a project module, and an import inside any function body, make
a router escaping. A router that nothing refers to stays an RCH002 finding.

The case `corpus/frameworks/router_registry_through_factory` fails on revision 53.

MODEL_REVISION becomes `python-fastapi-dishka/54`.
