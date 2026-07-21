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


def _keepalive_session():
    """A requests.Session whose sockets have TCP keep-alive enabled, so the
    connection survives the brief idle wait between fetching an Anubis challenge
    and submitting it. Anubis binds the challenge to the connection; if the
    socket drops during the wait the reconnect fails the proof ("invalid
    response"). Falls back to a plain session if the adapter can't be built."""
    import socket
    import requests
    from requests.adapters import HTTPAdapter

    opts = [(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)]
    for name, value in (("TCP_KEEPIDLE", 1), ("TCP_KEEPINTVL", 1), ("TCP_KEEPCNT", 8)):
        num = getattr(socket, name, None)
        if num is not None:
            opts.append((socket.IPPROTO_TCP, num, value))

    class _KeepAliveAdapter(HTTPAdapter):
        def init_poolmanager(self, *args, **kwargs):
            kwargs["socket_options"] = opts
            return super().init_poolmanager(*args, **kwargs)

    session = requests.Session()
    try:
        adapter = _KeepAliveAdapter()
        session.mount("https://", adapter)
        session.mount("http://", adapter)
    except Exception:
        pass
    return session


class CsfdClient:
    def __init__(self, cache_dir=None, ttl_seconds=604800, min_interval=1.0,
                 sleep=time.sleep, session=None, solve_delays=None):
        self._cache_dir = cache_dir
        self._ttl = ttl_seconds
        self._min_interval = min_interval
        self._sleep = sleep
        self._last_request = 0.0
        # Anubis wants a MINIMUM real time before submit ("insufficent time") but
        # the challenge also goes stale quickly ("invalid response"), so the valid
        # window is narrow. Sweep several submit delays and use the first the
        # server accepts; each is logged so the working value can be pinned.
        self._solve_delays = solve_delays or [0.3, 0.5, 0.7, 0.9]
        if session is not None:
            self._session = session
        else:
            self._session = _keepalive_session()
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

    def _fetch_with_anubis(self, url):
        html = self._raw_get(url)
        attempts = 0
        while anubis.is_trap(html) and attempts < len(self._solve_delays):
            delay = self._solve_delays[attempts]
            attempts += 1
            issued_at = time.time()
            ch = anubis.parse_challenge(html)
            issued_ip = ch["metadata"].get("X-Real-Ip")
            response_hash, nonce = anubis.solve(ch["random_data"], ch["difficulty"])
            # Anubis wants a MINIMUM real time before submit ("insufficent time")
            # but the challenge/connection also goes stale quickly ("invalid
            # response"), so sweep submit delays and stop at the first accepted.
            wait = delay - (time.time() - issued_at)
            if wait > 0:
                self._sleep(wait)
            elapsed_ms = max(1, int((time.time() - issued_at) * 1000))
            log.warning(
                "anubis: solving id=%s difficulty=%s delay=%.2f elapsed_ms=%s "
                "issued X-Real-Ip=%s randomData=%s nonce=%s response=%s",
                ch["id"], ch["difficulty"], delay, elapsed_ms,
                issued_ip, ch["random_data"], nonce, response_hash)
            pass_url = anubis.pass_challenge_url(
                BASE_URL, ch["id"], response_hash, nonce, url, elapsed_ms=elapsed_ms)
            try:
                # No throttle: ride the same keep-alive connection as the fetch.
                self._raw_get(pass_url, throttle=False)  # jar captures auth cookie
            except Exception as exc:
                resp = getattr(exc, "response", None)
                status = getattr(resp, "status_code", None)
                reason = anubis.error_reason(resp.text) if resp is not None else None
                import requests as _rq
                log.warning(
                    "anubis: pass-challenge REJECTED delay=%.2f status=%s reason=%r "
                    "cookies=[%s] requests=%s",
                    delay, status, reason,
                    ",".join(sorted(self._session.cookies.keys())),
                    getattr(_rq, "__version__", "?"))
                # Try the next delay with a fresh challenge instead of giving up.
                html = self._raw_get(url)
                continue
            log.warning("anubis: PASSED at delay=%.2f (elapsed_ms=%s)", delay, elapsed_ms)
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
