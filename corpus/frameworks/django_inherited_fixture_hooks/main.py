from unittest import TestCase

from django.test import TransactionTestCase
from django.test.testcases import TestCase as DatabaseCase
from hooks import _ClassHooks, _DormantHooks, _InstanceHooks, _PlainHooks, _ShadowedHooks


class LegacyCase(_InstanceHooks, TransactionTestCase):
    pass


class CurrentCase(_ClassHooks, _ShadowedHooks, DatabaseCase):
    pass


class _DormantCase(_DormantHooks, TransactionTestCase):
    pass


class PlainCase(_PlainHooks, TestCase):
    pass


def main():
    LegacyCase().run()
    CurrentCase().run()
    PlainCase().run()


if __name__ == "__main__":
    main()
