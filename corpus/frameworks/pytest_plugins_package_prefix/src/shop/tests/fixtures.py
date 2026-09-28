import pytest
from shop.orders import total


@pytest.fixture
def order() -> int:
    return total([1, 2])


@pytest.fixture
def stale_order() -> int:
    return 0
