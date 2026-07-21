import json
import pytest
from fetcher import AnubisFetcher
import anubis


class FakeResponse:
    def __init__(self, text):
        self.text = text
    def raise_for_status(self):
        pass


def _trap():
    ch = {"rules": {"difficulty": 1},
          "challenge": {"id": "x", "randomData": "abc", "difficulty": 1}}
    return ('<script id="anubis_challenge" type="application/json">'
            + json.dumps(ch) + "</script>")


class ScriptedSession:
    def __init__(self):
        self.passed = False
        self.calls = []
    def get(self, url, headers=None, timeout=None):
        self.calls.append(url)
        if "pass-challenge" in url:
            self.passed = True
            return FakeResponse("<html>ok</html>")
        if not self.passed:
            return FakeResponse(_trap())
        return FakeResponse("<html><h1>Matrix</h1></html>")


def test_get_returns_page_directly_when_not_trapped():
    class S:
        def get(self, url, headers=None, timeout=None):
            return FakeResponse("<html>clean</html>")
    f = AnubisFetcher(min_interval=0, session=S())
    assert f.get("https://www.csfd.cz/film/1/") == "<html>clean</html>"


def test_get_solves_trap_then_returns_real_page():
    s = ScriptedSession()
    f = AnubisFetcher(min_interval=0, session=s)
    html = f.get("https://www.csfd.cz/film/1/")
    assert "<h1>Matrix</h1>" in html
    assert any("pass-challenge" in u for u in s.calls)


def test_get_raises_when_never_passes():
    class AlwaysTrap:
        def get(self, url, headers=None, timeout=None):
            if "pass-challenge" in url:
                return FakeResponse("<html>ok</html>")
            return FakeResponse(_trap())
    f = AnubisFetcher(min_interval=0, session=AlwaysTrap(), max_attempts=2)
    with pytest.raises(anubis.AnubisError):
        f.get("https://www.csfd.cz/film/1/")
