from fastapi import FastAPI

from svc.main import app


def enable_profiling(application: FastAPI) -> None:
    application.state.profiling = True


enable_profiling(app)
