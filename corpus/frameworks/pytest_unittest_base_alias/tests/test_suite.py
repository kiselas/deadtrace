from .util import TestCase


class Suite(TestCase):
    def test_value(self) -> None:
        self.assertEqual(1, 1)
