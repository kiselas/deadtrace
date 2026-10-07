import nox


def uv_sync(session):
    session.run("uv", "sync")


@nox.session
def tests(session):
    uv_sync(session)
    session.run("pytest")
