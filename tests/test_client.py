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
    def get(self, url, headers=None, timeout=None):
        self.calls.append({"url": url, "headers": headers})
        return FakeResponse(self.text)


def test_get_returns_html_and_sends_polite_headers():
    s = FakeSession("<html>hi</html>")
    c = CsfdClient(cache_dir=None, session=s, min_interval=0)
    html = c.get("https://www.csfd.cz/film/1/")
    assert html == "<html>hi</html>"
    hdrs = s.calls[0]["headers"]
    assert "Mozilla" in hdrs["User-Agent"]
    assert hdrs["Accept-Language"].startswith("cs")


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


import json as _json
from csfd import anubis as _anubis


class ScriptedAnubisSession:
    """First hit on a page → trap; after pass-challenge is called → real HTML."""
    def __init__(self):
        self.passed = False
        self.calls = []

    def get(self, url, headers=None, timeout=None):
        self.calls.append(url)
        if "pass-challenge" in url:
            self.passed = True
            return FakeResponse("<html>redirected</html>")
        if not self.passed:
            challenge = {
                "rules": {"difficulty": 1},
                "challenge": {"id": "x", "randomData": "abc123", "difficulty": 1},
            }
            return FakeResponse(
                '<script id="anubis_challenge" type="application/json">'
                + _json.dumps(challenge) + "</script>")
        return FakeResponse("<html><h1>Matrix</h1></html>")


def test_get_solves_anubis_trap_and_returns_real_page():
    s = ScriptedAnubisSession()
    c = CsfdClient(cache_dir=None, session=s, min_interval=0)
    html = c.get("https://www.csfd.cz/film/9499/")
    assert "<h1>Matrix</h1>" in html
    assert any("pass-challenge" in u for u in s.calls)


def test_get_raises_when_anubis_never_passes():
    class AlwaysTrap:
        def get(self, url, headers=None, timeout=None):
            if "pass-challenge" in url:
                return FakeResponse("<html>ok</html>")
            challenge = {"rules": {"difficulty": 1},
                         "challenge": {"id": "x", "randomData": "abc", "difficulty": 1}}
            return FakeResponse(
                '<script id="anubis_challenge" type="application/json">'
                + _json.dumps(challenge) + "</script>")
    import pytest
    c = CsfdClient(cache_dir=None, session=AlwaysTrap(), min_interval=0,
                   max_solve_attempts=2)
    with pytest.raises(_anubis.AnubisError):
        c.get("https://www.csfd.cz/film/1/")
