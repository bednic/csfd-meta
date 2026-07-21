import threading
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer

from app import make_handler, is_allowed_url
import anubis


class FakeFetcher:
    def __init__(self, html="<html>ok</html>", error=None):
        self.html = html
        self.error = error
        self.calls = []
    def get(self, url):
        self.calls.append(url)
        if self.error:
            raise self.error
        return self.html


def _server(fetcher):
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(fetcher))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def _get(httpd, path):
    port = httpd.server_address[1]
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d%s" % (port, path)) as r:
            return r.status, r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")


def test_is_allowed_url():
    assert is_allowed_url("https://www.csfd.cz/film/1/")
    assert not is_allowed_url("https://evil.com/")
    assert not is_allowed_url("http://www.csfd.cz/")
    assert not is_allowed_url("")


def test_health():
    httpd = _server(FakeFetcher())
    try:
        assert _get(httpd, "/health") == (200, "ok")
    finally:
        httpd.shutdown()


def test_fetch_returns_html():
    f = FakeFetcher(html="<html><h1>Matrix</h1></html>")
    httpd = _server(f)
    try:
        status, body = _get(
            httpd, "/fetch?url=https%3A%2F%2Fwww.csfd.cz%2Ffilm%2F1%2F")
        assert status == 200
        assert "<h1>Matrix</h1>" in body
        assert f.calls == ["https://www.csfd.cz/film/1/"]
    finally:
        httpd.shutdown()


def test_fetch_rejects_non_csfd():
    httpd = _server(FakeFetcher())
    try:
        assert _get(httpd, "/fetch?url=https%3A%2F%2Fevil.com%2F")[0] == 400
    finally:
        httpd.shutdown()


def test_fetch_missing_url():
    httpd = _server(FakeFetcher())
    try:
        assert _get(httpd, "/fetch")[0] == 400
    finally:
        httpd.shutdown()


def test_fetch_fetcher_error_is_502():
    httpd = _server(FakeFetcher(error=anubis.AnubisError("boom")))
    try:
        status, _ = _get(
            httpd, "/fetch?url=https%3A%2F%2Fwww.csfd.cz%2Ffilm%2F1%2F")
        assert status == 502
    finally:
        httpd.shutdown()
