# ADR-0123: Routers named through imports in the including function

**Status:** Proposed, 2026-11-02; model revision 95. Field evaluation pending.

## Context

An application factory often imports its route modules in its own body, so that importing the
package does not import every route:

```python
def create_app():
    app = fastapi.FastAPI()
    from chat_api.routes import messages

    app.include_router(messages.router)
    return app
```

The framework model resolved the argument of `include_router` only through the imports at the
top of the module. `messages` was unknown there, so the call was recorded as an unknown include
(ADR-0017). An unknown include keeps every escaping router possibly published (ADR-0072), and a
router counts as escaping when an import names it. That import was resolved with the importer's
own package as the base, not through the nested-package rule the module imports use (ADR-0065).
In a service kept in a subdirectory, such as `src/backend/notes_service` installed from
`src/backend`, `notes_service.routes.messages` names no project module, so the router was not
escaping either: its routes were reported as RCH002 and the models only they use as RCH001.

On model 94 one reviewed development project of the public cohorts had 32 false members from this
alone: the router behind the factory and 25 request and response models of its routes.

## Decision

When the argument of an `include_router` call in a function names something through an import
of that function's body, or of a function enclosing it, the import's target is taken, resolved
by the same import rules as the module's top-level imports (ADR-0017, ADR-0022, ADR-0065). The
innermost binding of a name wins; otherwise the module's imports apply as before.

Resolving the call adds an include where the model had an unknown one. It can make a router
published that the unknown include kept only possibly published, and it removes that unknown
include's protection of the other escaping routers when no other unknown include remains. A
router that only such an unknown include protected is now reported if nothing includes it.

The case `corpus/frameworks/router_imported_in_nested_factory` fails on revision 94: the included
router and its request model are reported.

MODEL_REVISION becomes `python-fastapi-dishka/95`.
