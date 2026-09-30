import pytest


@pytest.fixture
def clock() -> int:
    return 1


def unused_fixture() -> int:
    return 2
