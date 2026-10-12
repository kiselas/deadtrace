def _round(value: float) -> float:
    return round(value, 2)


def discounted(price: float) -> float:
    """Price after the house discount.

    >>> _round(discounted(10.0))
    9.0
    """
    return price * 0.9


def _never_documented(value: float) -> float:
    return value
