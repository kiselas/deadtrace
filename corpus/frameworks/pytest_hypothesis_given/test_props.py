from hypothesis import given
from hypothesis import strategies as st


@given(st.integers())
def test_positive(value: int) -> None:
    assert value is not None


@given(name=st.text())
def test_named(name: str) -> None:
    assert name is not None


class TestBox:
    @given(st.integers(), st.integers())
    def test_pair(self, first: int, second: int) -> None:
        assert first + second == second + first
