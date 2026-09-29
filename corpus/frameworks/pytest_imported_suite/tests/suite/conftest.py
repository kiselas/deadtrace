import pytest


@pytest.fixture
def base_url() -> str:
    return "https://example.test/"


@pytest.fixture
def session_cookie() -> str:
    return "plain"
