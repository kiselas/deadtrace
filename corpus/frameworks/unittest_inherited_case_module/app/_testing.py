import unittest

from app._auth import check


class BaseAuthTests(unittest.TestCase):
    def token(self):
        raise NotImplementedError

    def test_check(self):
        self.assertTrue(check(self.token()))
