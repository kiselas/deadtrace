import pytest


class BaseCartTest:
    @pytest.fixture
    def items(self):
        return [1, 2]
