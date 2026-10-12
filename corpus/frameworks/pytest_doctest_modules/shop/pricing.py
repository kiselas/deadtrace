def _round(value: float) -> float:
    return round(value, 2)


def discounted(price: float) -> float:
    """Price after the house discount.

    >>> _round(discounted(10.0))
    9.0
    """
    return price * 0.9


def total(items: list[float]) -> float:
    """Sum of a basket.

    >>> from tests.examples import sample_basket
    >>> total(sample_basket())
    10.0
    """
    return sum(items)


def _never_documented(value: float) -> float:
    return value
