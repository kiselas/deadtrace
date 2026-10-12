import pytest
from apilib import BaseApi, SetupError


def test_invalid():
    with pytest.raises(SetupError):

        class _Invalid(BaseApi):
            url = "x"


def test_other():
    class _Unused(BaseApi):
        url = "y"
