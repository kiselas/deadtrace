import pytest


@pytest.fixture
def faker(request: pytest.FixtureRequest) -> int:
    return request.getfixturevalue("_session_value") + 1


@pytest.fixture(scope="session")
def _session_value() -> int:
    return 41


def _unused_helper() -> None:
    pass
