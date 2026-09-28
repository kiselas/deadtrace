from _meta import Meta


def test_meta() -> None:
    class Local(metaclass=Meta):
        VALUE = 1
