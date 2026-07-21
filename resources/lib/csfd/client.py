import hashlib
import json
import logging
import os
import time

from .urls import BASE_URL
from . import anubis

log = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"),
    "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
               "image/avif,image/webp,*/*;q=0.8"),
    "Accept-Language": "cs-CZ,cs;q=0.9,en;q=0.7",
    "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Linux"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Upgrade-Insecure-Requests": "1",
}


class CsfdClient:
    def __init__(self, cache_dir=None, ttl_seconds=604800, min_interval=1.0,
                 sleep=time.sleep, session=None, max_solve_attempts=3):
        self._cache_dir = cache_dir
        self._ttl = ttl_seconds
        self._min_interval = min_interval
        self._sleep = sleep
        self._last_request = 0.0
        self._max_solve_attempts = max_solve_attempts
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

    def _raw_get(self, url, throttle=True):
        if throttle:
            self._throttle()
        resp = self._session.get(url, headers=_HEADERS, timeout=10)
        resp.raise_for_status()
        self._last_request = time.time()
        return resp.text

    def _probe_real_ip(self, url):
        """Diagnostic: re-fetch a fresh challenge and return the X-Real-Ip that
        csfd.cz reports for us right now, to detect whether our source IP
        changed between challenge issuance and pass-challenge submission."""
        try:
            return anubis.parse_challenge(
                self._raw_get(url))["metadata"].get("X-Real-Ip")
        except Exception:
            return None

    def _fetch_with_anubis(self, url):
        html = self._raw_get(url)
        attempts = 0
        while anubis.is_trap(html) and attempts < self._max_solve_attempts:
            attempts += 1
            issued_at = time.time()
            ch = anubis.parse_challenge(html)
            issued_ip = ch["metadata"].get("X-Real-Ip")
            response_hash, nonce = anubis.solve(ch["random_data"], ch["difficulty"])
            # Report the ACTUAL time spent, not a hardcoded value. Anubis rejects
            # "insufficent time" when the claimed elapsedTime exceeds the real time
            # since the challenge was issued (we can't claim 1000ms if ~150ms passed).
            elapsed_ms = max(1, int((time.time() - issued_at) * 1000))
            log.warning(
                "anubis: solving id=%s difficulty=%s issued X-Real-Ip=%s "
                "randomData=%s nonce=%s response=%s elapsed_ms=%s",
                ch["id"], ch["difficulty"], issued_ip,
                ch["random_data"], nonce, response_hash, elapsed_ms)
            pass_url = anubis.pass_challenge_url(
                BASE_URL, ch["id"], response_hash, nonce, url, elapsed_ms=elapsed_ms)
            try:
                # Submit immediately, with NO throttle sleep, so the pass-challenge
                # rides the SAME keep-alive connection as the challenge fetch.
                # Anubis binds the challenge to the connection/TLS fingerprint; a
                # sleep here lets the socket drop and the retry connect with a
                # different fingerprint, which the server rejects as
                # "invalid response". Solving is sub-millisecond at difficulty 1.
                self._raw_get(pass_url, throttle=False)  # jar captures auth cookie
            except Exception as exc:
                resp = getattr(exc, "response", None)
                status = getattr(resp, "status_code", None)
                reason = anubis.error_reason(resp.text) if resp is not None else None
                recheck_ip = self._probe_real_ip(url)
                import requests as _rq
                log.warning(
                    "anubis: pass-challenge REJECTED status=%s reason=%r "
                    "issued X-Real-Ip=%s recheck X-Real-Ip=%s ip_changed=%s "
                    "cookies=[%s] requests=%s",
                    status, reason, issued_ip, recheck_ip,
                    issued_ip != recheck_ip,
                    ",".join(sorted(self._session.cookies.keys())),
                    getattr(_rq, "__version__", "?"))
                raise
            html = self._raw_get(url)
        if anubis.is_trap(html):
            raise anubis.AnubisError(
                f"failed to pass Anubis after {attempts} attempts: {url}")
        return html

    def get(self, url, ttl=None):
        ttl = self._ttl if ttl is None else ttl
        cached = self._read_cache(url, ttl)
        if cached is not None:
            return cached
        html = self._fetch_with_anubis(url)
        self._write_cache(url, html)
        return html
