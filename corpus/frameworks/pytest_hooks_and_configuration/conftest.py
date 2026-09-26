import asyncio

import pytest


def pytest_configure(config: object) -> None:
    pass


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
