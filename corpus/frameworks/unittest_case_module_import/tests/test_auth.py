from unittest.case import TestCase

from app._auth import check


class AuthTests(TestCase):
    def test_check(self):
        self.assertTrue(check("x"))

    def helper(self):
        return "x"
