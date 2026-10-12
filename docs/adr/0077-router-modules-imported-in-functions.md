# ADR-0077: Router modules imported inside functions

**Status:** Accepted, 2026-10-12; model revision 60. Extends ADR-0072.

ADR-0072 counts a router as escaping when another module reads it as `module.router` through a
top-level import, or imports it by name inside a function. `register_routers` in one cohort project
imports router *modules* inside the function under other names (`from app.routers import payments
as payments_router`) and includes `payments_router.router`; 14 reviewed RCH002 findings were false.

An attribute read `name.router` now also counts when `name` is bound by an import inside any function
of the reading module. A router that nothing refers to stays an RCH002 finding.

The case `corpus/frameworks/router_registry_through_factory` (its `billing` router) fails on
revision 59.

MODEL_REVISION becomes `python-fastapi-dishka/60`.
