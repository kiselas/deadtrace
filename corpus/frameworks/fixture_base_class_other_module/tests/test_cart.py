from app.cart import total

from .base import BaseCartTest


class TestCart(BaseCartTest):
    def test_total(self, items):
        assert total(items) == 3
