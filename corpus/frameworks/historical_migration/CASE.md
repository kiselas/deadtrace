# Historical migration callback

A Django `RunPython` callback can be required long after normal application call paths stop using
it. The callback and its helper are conservative external execution roots and must not become
dead-code findings in a FastAPI service that shares the repository.
