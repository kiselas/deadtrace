import pytest
from app import test_only_helper


@pytest.fixture
def value() -> str:
    return test_only_helper()
