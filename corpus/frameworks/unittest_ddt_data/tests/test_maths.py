import unittest

from app.maths import double
from ddt import data, ddt, unpack


@ddt
class DoubleTest(unittest.TestCase):
    @data((1, 2), (2, 4))
    @unpack
    def test_double(self, value, expected):
        self.assertEqual(double(value), expected)
