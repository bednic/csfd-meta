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
    c = CsfdClient(cache_dir=None, session=s, min_interval=0,
                   sleep=lambda n: None)
    html = c.get("https://www.csfd.cz/film/9499/")
    assert "<h1>Matrix</h1>" in html
    assert any("pass-challenge" in u for u in s.calls)


def test_pass_challenge_waits_min_solve_time_then_submits():
    """Anubis rejects "insufficent time" if we submit too fast, and "invalid
    response" if the connection drops. So the pass-challenge must be preceded by
    the minimum-solve wait (satisfying the timing gate) and nothing else."""
    timeline = []

    class TimelineSession:
        def __init__(self):
            self.passed = False
        def get(self, url, headers=None, timeout=None):
            timeline.append(("get", url))
            if "pass-challenge" in url:
                self.passed = True
                return FakeResponse("<html>ok</html>")
            if not self.passed:
                ch = {"rules": {"difficulty": 1},
                      "challenge": {"id": "x", "randomData": "abc", "difficulty": 1}}
                return FakeResponse(
                    '<script id="anubis_challenge" type="application/json">'
                    + _json.dumps(ch) + "</script>")
            return FakeResponse("<html><h1>Matrix</h1></html>")

    c = CsfdClient(cache_dir=None, session=TimelineSession(), min_interval=0,
                   solve_delays=[0.5],
                   sleep=lambda n: timeline.append(("sleep", n)))
    c.get("https://www.csfd.cz/film/1/")
    pass_idx = next(i for i, (k, u) in enumerate(timeline)
                    if k == "get" and "pass-challenge" in u)
    kind, val = timeline[pass_idx - 1]
    assert kind == "sleep" and val >= 0.4  # the minimum-solve wait, ~0.5s


def test_solve_sweeps_delays_until_pass_accepted():
    """A rejected pass-challenge (e.g. 403 'invalid response') should not abort;
    the client tries the next delay with a fresh challenge and stops when the
    server accepts one."""
    class RejectError(Exception):
        def __init__(self, resp):
            self.response = resp

    class RejectResponse:
        def __init__(self, text):
            self.text = text
        def raise_for_status(self):
            raise RejectError(self)

    ch_json = ('<script id="anubis_challenge" type="application/json">'
               + _json.dumps({"rules": {"difficulty": 1},
                              "challenge": {"id": "x", "randomData": "abc",
                                            "difficulty": 1}}) + "</script>")

    class SweepSession:
        cookies = type("C", (), {"keys": staticmethod(lambda: [])})()
        def __init__(self):
            self.pass_attempts = 0
            self.passed = False
        def get(self, url, headers=None, timeout=None):
            if "pass-challenge" in url:
                self.pass_attempts += 1
                if self.pass_attempts < 3:          # reject the first two delays
                    return RejectResponse("<p>invalid response.</p>")
                self.passed = True                  # accept the third
                return FakeResponse("<html>ok</html>")
            if not self.passed:
                return FakeResponse(ch_json)
            return FakeResponse("<html><h1>Matrix</h1></html>")

    s = SweepSession()
    c = CsfdClient(cache_dir=None, session=s, min_interval=0,
                   solve_delays=[0.1, 0.2, 0.3, 0.4], sleep=lambda n: None)
    html = c.get("https://www.csfd.cz/film/1/")
    assert "<h1>Matrix</h1>" in html
    assert s.pass_attempts == 3


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
                   solve_delays=[0.1, 0.1], sleep=lambda n: None)
    with pytest.raises(_anubis.AnubisError):
        c.get("https://www.csfd.cz/film/1/")
