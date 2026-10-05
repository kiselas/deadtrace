import pytest
from flask import Flask
from lib import Api


@pytest.fixture
def app():
    application = Flask(__name__)
    Api().register("x")
    return application
