import logging
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from fetcher import AnubisFetcher

log = logging.getLogger(__name__)

ALLOWED_HOST = "www.csfd.cz"


def is_allowed_url(url):
    if not url:
        return False
    try:
        p = urlparse(url)
    except ValueError:
        return False
    return p.scheme == "https" and p.netloc == ALLOWED_HOST


def make_handler(fetcher):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code, body, ctype="text/plain; charset=utf-8"):
            data = body.encode("utf-8") if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == "/health":
                self._send(200, "ok")
                return
            if parsed.path == "/fetch":
                url = (parse_qs(parsed.query).get("url") or [""])[0]
                if not is_allowed_url(url):
                    self._send(400, "missing or disallowed url")
                    return
                try:
                    html = fetcher.get(url)
                except Exception as exc:
                    log.warning("fetch failed for %s: %s", url, exc)
                    self._send(502, "fetch failed: %s" % exc)
                    return
                self._send(200, html, "text/html; charset=utf-8")
                return
            self._send(404, "not found")

        def log_message(self, fmt, *args):
            log.info("%s - %s", self.address_string(), fmt % args)

    return Handler


def serve(port=None, fetcher=None):
    port = int(port if port is not None else os.environ.get("PORT", "9753"))
    fetcher = fetcher or AnubisFetcher()
    httpd = ThreadingHTTPServer(("0.0.0.0", port), make_handler(fetcher))
    log.info("anubis-relay listening on 0.0.0.0:%d", port)
    httpd.serve_forever()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    serve()
