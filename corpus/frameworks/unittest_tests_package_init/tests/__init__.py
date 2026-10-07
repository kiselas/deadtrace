import unittest

from app.auth import check


class AuthTest(unittest.TestCase):
    def test_check(self):
        self.assertTrue(check("x"))
