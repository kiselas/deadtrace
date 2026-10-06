from demo_kit import Client


def test_client():
    assert Client().fetch("a") == "a"
