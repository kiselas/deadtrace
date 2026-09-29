import unittest


class Checks(unittest.TestCase):
    def testValue(self) -> None:
        self.assertEqual(1, 1)


def unused() -> str:
    return "never called"


if __name__ == "__main__":
    unittest.main()
