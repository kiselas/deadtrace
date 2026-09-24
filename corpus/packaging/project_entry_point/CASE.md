# PEP 621 project entry point

A statically declared console script is an external production root. Deadtrace reads its object
reference from `pyproject.toml` as data, resolves the function in a `src/` layout, and keeps its
transitive helper live without importing the package or invoking a build backend.
