from django.test import TestCase
from rest_framework.test import APITestCase


class ViewTest(TestCase):
    def test_value(self):
        assert True


class ApiTest(APITestCase):
    def test_value(self):
        assert True
