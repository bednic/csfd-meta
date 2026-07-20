import time
from csfd.client import CsfdClient


class FakeResponse:
    def __init__(self, text):
        self.text = text
    def raise_for_status(self):
        pass


class FakeSession:
    def __init__(self, text="<html>ok</html>"):
        self.text = text
        self.calls = []
    def get(self, url, headers=None, timeout=None, cookies=None):
        self.calls.append({"url": url, "headers": headers, "cookies": cookies})
        return FakeResponse(self.text)


def test_get_returns_html_and_sends_polite_headers():
    s = FakeSession("<html>hi</html>")
    c = CsfdClient(cache_dir=None, session=s, min_interval=0)
    html = c.get("https://www.csfd.cz/film/1/")
    assert html == "<html>hi</html>"
    hdrs = s.calls[0]["headers"]
    assert "Mozilla" in hdrs["User-Agent"]
    assert hdrs["Accept-Language"].startswith("cs")
    assert s.calls[0]["cookies"]  # consent cookie present


def test_cache_hit_avoids_second_request(tmp_path):
    s = FakeSession("<html>cached</html>")
    c = CsfdClient(cache_dir=str(tmp_path), session=s, min_interval=0)
    c.get("https://www.csfd.cz/film/1/")
    c.get("https://www.csfd.cz/film/1/")
    assert len(s.calls) == 1


def test_expired_cache_refetches(tmp_path):
    s = FakeSession("<html>x</html>")
    c = CsfdClient(cache_dir=str(tmp_path), session=s, min_interval=0, ttl_seconds=0)
    c.get("https://www.csfd.cz/film/1/")
    c.get("https://www.csfd.cz/film/1/")
    assert len(s.calls) == 2


def test_rate_limiter_sleeps_between_requests():
    slept = []
    s = FakeSession()
    c = CsfdClient(cache_dir=None, session=s, min_interval=2.0,
                   sleep=lambda n: slept.append(n))
    c.get("https://www.csfd.cz/film/1/")
    c.get("https://www.csfd.cz/film/2/")
    assert any(n > 0 for n in slept)
