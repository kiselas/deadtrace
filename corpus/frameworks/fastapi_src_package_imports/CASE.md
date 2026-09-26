# FastAPI application importing a `src` package

Some projects put the repository root on the import path and import the `src` directory as a
package: `from src.api.routes import router`. The router is then included by the application,
so its route runs and must not be reported as unpublished or unreached.

A `src` directory is more often a source root whose packages are imported by their own names;
there the directory name is not part of module names. The unsafe outcome is treating every
`src.` import as external, which reports an included router as `RCH002` and its routes as dead.
A helper that nothing calls is still reported, so the case cannot pass by weakening the world.
