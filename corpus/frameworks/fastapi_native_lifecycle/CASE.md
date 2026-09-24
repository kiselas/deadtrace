# FastAPI native dependencies and lifecycle

An operation-level dependency is executed even when its value is ignored. Lifespan cleanup,
background callbacks, and Pydantic hooks retain their transitive helpers.
