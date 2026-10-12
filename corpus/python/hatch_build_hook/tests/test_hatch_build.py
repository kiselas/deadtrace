from hatch_build import _get_version


def test_version():
    assert _get_version() == "0.1.0"
