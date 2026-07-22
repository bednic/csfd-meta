import hashlib
import json
import os
import time
from urllib.parse import quote


class CsfdClient:
    """Fetch csfd.cz HTML through the Anubis relay and cache it. All Anubis
    solving happens on the relay (the anubis-relay service); the Kodi device
    cannot pass the wall itself."""

    def __init__(self, relay_url, cache_dir=None, ttl_seconds=604800, session=None):
        self._relay = (relay_url or "").rstrip("/")
        self._cache_dir = cache_dir
        self._ttl = ttl_seconds
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

    def _fetch(self, url):
        if not self._relay:
            raise RuntimeError("relay_url is not configured (see addon settings)")
        full = self._relay + "/fetch?url=" + quote(url, safe="")
        resp = self._session.get(full, timeout=30)
        resp.raise_for_status()
        return resp.text

    def get(self, url, ttl=None):
        ttl = self._ttl if ttl is None else ttl
        cached = self._read_cache(url, ttl)
        if cached is not None:
            return cached
        html = self._fetch(url)
        self._write_cache(url, html)
        return html
