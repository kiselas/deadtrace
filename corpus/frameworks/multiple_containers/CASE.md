# Multiple FastAPI applications and Dishka containers

Each application is paired with its own container. Providers for the same demanded type remain
world-local; a binding attached to the second app cannot satisfy the first app.
