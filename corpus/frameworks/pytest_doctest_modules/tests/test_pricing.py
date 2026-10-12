from shop.pricing import discounted


def test_discounted():
    assert discounted(10.0) == 9.0
