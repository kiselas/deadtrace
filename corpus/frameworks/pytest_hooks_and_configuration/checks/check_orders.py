from orders import total


def test_total() -> None:
    assert total([1]) == 1
