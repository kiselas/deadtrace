# Bounded FastAPI application factory

A common `create_app` function constructs one FastAPI instance, includes a known router, attaches a
known global Dishka container, and returns that instance unchanged. Deadtrace expands only this
bounded static shape; it does not execute the factory.
