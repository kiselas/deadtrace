import pytest


@pytest.fixture(scope="session")
def base_url() -> str:
    return "https://shared.test/"


@pytest.fixture
def session_cookie() -> str:
    return "cookie"


@pytest.fixture
def forgotten() -> str:
    return "unused"
