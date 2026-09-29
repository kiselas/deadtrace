from pages import open_page


def test_open(base_url: str) -> None:
    assert open_page(base_url)


class TestPages:
    def test_reload(self, base_url: str, session_cookie: str) -> None:
        assert open_page(base_url) and session_cookie
