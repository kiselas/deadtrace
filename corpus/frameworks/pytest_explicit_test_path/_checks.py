from app.pricing import price


def test_price():
    assert price(1) == 1


class TestPrice:
    def test_zero(self):
        assert price(0) == 0
