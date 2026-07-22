import pytest
from csfd.client import CsfdClient


class FakeResponse:
    def __init__(self, text, status=200):
        self.text = text
        self.status_code = status
    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("HTTP %d" % self.status_code)


class FakeSession:
    def __init__(self, response=None):
        self.response = response or FakeResponse("<html>hi</html>")
        self.calls = []
    def get(self, url, headers=None, timeout=None):
        self.calls.append(url)
        return self.response


def test_get_fetches_via_relay_and_returns_body():
    s = FakeSession(FakeResponse("<html>page</html>"))
    c = CsfdClient("http://nas:9753", cache_dir=None, session=s)
    html = c.get("https://www.csfd.cz/film/1/")
    assert html == "<html>page</html>"
    assert s.calls == [
        "http://nas:9753/fetch?url=https%3A%2F%2Fwww.csfd.cz%2Ffilm%2F1%2F"]


def test_trailing_slash_in_relay_url_is_normalised():
    s = FakeSession()
    c = CsfdClient("http://nas:9753/", cache_dir=None, session=s)
    c.get("https://www.csfd.cz/x")
    assert s.calls[0].startswith("http://nas:9753/fetch?url=")


def test_cache_hit_avoids_second_relay_call(tmp_path):
    s = FakeSession(FakeResponse("<html>cached</html>"))
    c = CsfdClient("http://nas:9753", cache_dir=str(tmp_path), session=s)
    c.get("https://www.csfd.cz/film/1/")
    c.get("https://www.csfd.cz/film/1/")
    assert len(s.calls) == 1


def test_expired_cache_refetches(tmp_path):
    s = FakeSession(FakeResponse("<html>x</html>"))
    c = CsfdClient("http://nas:9753", cache_dir=str(tmp_path),
                   ttl_seconds=0, session=s)
    c.get("https://www.csfd.cz/film/1/")
    c.get("https://www.csfd.cz/film/1/")
    assert len(s.calls) == 2


def test_non_200_raises():
    s = FakeSession(FakeResponse("nope", status=502))
    c = CsfdClient("http://nas:9753", cache_dir=None, session=s)
    with pytest.raises(Exception):
        c.get("https://www.csfd.cz/film/1/")


def test_no_relay_url_raises():
    c = CsfdClient("", cache_dir=None, session=FakeSession())
    with pytest.raises(RuntimeError):
        c.get("https://www.csfd.cz/film/1/")
