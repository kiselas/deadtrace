import pytest


def make_first():
    return 1


def make_second():
    return 2


class TestFirst:
    @pytest.fixture
    def value(self):
        return make_first()

    def test_value(self, value):
        assert value == 1


class TestSecond:
    @pytest.fixture
    def value(self):
        return make_second()

    def test_value(self, value):
        assert value == 2
