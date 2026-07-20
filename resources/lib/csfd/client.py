import hashlib
import json
import os
import time

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/122.0 Safari/537.36")
_HEADERS = {"User-Agent": _UA, "Accept-Language": "cs,sk;q=0.8,en;q=0.5"}
# CSFD stores consent in this cookie; sending it skips the GDPR interstitial.
_COOKIES = {"cpex_consent": "1", "euconsent-v2": "1"}


class CsfdClient:
    def __init__(self, cache_dir=None, ttl_seconds=604800, min_interval=1.0,
                 sleep=time.sleep, session=None):
        self._cache_dir = cache_dir
        self._ttl = ttl_seconds
        self._min_interval = min_interval
        self._sleep = sleep
        self._last_request = 0.0
        if session is not None:
            self._session = session
        else:
            import requests
            self._session = requests.Session()
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)

    def _cache_path(self, url):
        key = hashlib.sha1(url.encode("utf-8")).hexdigest()
        return os.path.join(self._cache_dir, key + ".json")

    def _read_cache(self, url, ttl):
        if not self._cache_dir:
            return None
        path = self._cache_path(url)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as fh:
                blob = json.load(fh)
        except (OSError, ValueError):
            return None
        if (time.time() - blob["ts"]) > ttl:
            return None
        return blob["html"]

    def _write_cache(self, url, html):
        if not self._cache_dir:
            return
        try:
            with open(self._cache_path(url), "w", encoding="utf-8") as fh:
                json.dump({"ts": time.time(), "html": html}, fh)
        except OSError:
            pass

    def _throttle(self):
        if self._min_interval <= 0:
            return
        wait = self._min_interval - (time.time() - self._last_request)
        if wait > 0:
            self._sleep(wait)

    def get(self, url, ttl=None):
        ttl = self._ttl if ttl is None else ttl
        cached = self._read_cache(url, ttl)
        if cached is not None:
            return cached
        self._throttle()
        resp = self._session.get(url, headers=_HEADERS, timeout=10,
                                 cookies=_COOKIES)
        resp.raise_for_status()
        self._last_request = time.time()
        html = resp.text
        self._write_cache(url, html)
        return html
