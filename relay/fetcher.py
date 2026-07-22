import threading
import time

import requests

import anubis

BASE_URL = "https://www.csfd.cz"

_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"),
    "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
               "image/avif,image/webp,*/*;q=0.8"),
    "Accept-Language": "cs-CZ,cs;q=0.9,en;q=0.7",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Upgrade-Insecure-Requests": "1",
}


class AnubisFetcher:
    """Fetch csfd.cz pages, solving the Anubis proof-of-work wall when
    challenged. Runs on a normal-fingerprint host where an immediate submit is
    accepted. One long-lived session reuses the auth cookie across calls, so
    the challenge is solved only occasionally."""

    def __init__(self, min_interval=1.0, sleep=time.sleep, session=None,
                 max_attempts=3):
        self._min_interval = min_interval
        self._sleep = sleep
        self._last_request = 0.0
        self._max_attempts = max_attempts
        self._session = session if session is not None else requests.Session()
        self._lock = threading.Lock()

    def _throttle(self):
        if self._min_interval <= 0:
            return
        wait = self._min_interval - (time.time() - self._last_request)
        if wait > 0:
            self._sleep(wait)

    def _raw_get(self, url):
        self._throttle()
        resp = self._session.get(url, headers=_HEADERS, timeout=15,
                                 allow_redirects=False)
        resp.raise_for_status()
        self._last_request = time.time()
        return resp.text

    def get(self, url):
        with self._lock:
            html = self._raw_get(url)
            attempts = 0
            while anubis.is_trap(html) and attempts < self._max_attempts:
                attempts += 1
                ch = anubis.parse_challenge(html)
                response_hash, nonce = anubis.solve(ch["random_data"], ch["difficulty"])
                pass_url = anubis.pass_challenge_url(
                    BASE_URL, ch["id"], response_hash, nonce, url)
                self._raw_get(pass_url)   # session cookie jar captures the auth cookie
                html = self._raw_get(url)
            if anubis.is_trap(html):
                raise anubis.AnubisError(
                    "failed to pass Anubis after %d attempts: %s" % (attempts, url))
            return html
