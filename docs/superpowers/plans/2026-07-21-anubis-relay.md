# Anubis Relay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move Anubis proof-of-work solving off the fingerprint-blocked Android TV dongle onto a Dockerised LAN relay, and make the Kodi addon fetch csfd.cz pages through it.

**Architecture:** Thin relay (HTML proxy). A self-contained `relay/` service (stdlib `http.server`) solves Anubis on a normal-fingerprint host and returns raw HTML. The addon's `CsfdClient` is rewritten to fetch from the relay and cache; it contains no Anubis logic. Two deploy units in one repo; the relay ships as the Docker image `bednic/anubis-relay`.

**Tech Stack:** Python 3 (CPython ≥3.8, Kodi `xbmc.python` 3.0.1), `requests` (relay + addon), stdlib `http.server`, Docker, pytest.

## Global Constraints

- Relay listens on port **9753** (`PORT` env, default `9753`).
- Addon `relay_url` setting default: **`http://nas:9753`**.
- Relay image published as **`bednic/anubis-relay`** (tags `latest` + `0.2.0`).
- Relay SSRF guard: only fetch URLs with scheme `https` and host `www.csfd.cz`.
- Relay depends only on `requests` (no HTML-parsing libs; the relay does not parse).
- Addon version bumps to **`0.2.0`** in both `addon.xml` and `Makefile`.
- Addon tests run via root `pytest` (`pytest.ini`: `pythonpath = resources/lib`, `-m "not network"`). Relay tests run via `cd relay && pytest` (`relay/pytest.ini`: `pythonpath = .`).
- Relay modules are imported flat (`import anubis`, `from fetcher import ...`, `from app import ...`) — the relay is not a package.

---

### Task 1: Relay Anubis module + test relocation

Copy the Anubis primitives into the self-contained relay and set up its test config. The addon keeps its own copy for now (deleted in Task 5) so nothing breaks between tasks.

**Files:**
- Create: `relay/anubis.py` (copy of `resources/lib/csfd/anubis.py`)
- Create: `relay/pytest.ini`
- Create: `relay/tests/test_anubis.py` (copy of `tests/test_anubis.py`, import fixed)

**Interfaces:**
- Produces: module `anubis` with `is_trap(html)`, `parse_challenge(html) -> {"id","random_data","difficulty","metadata"}`, `solve(random_data, difficulty, max_iterations=8_000_000) -> (hash, nonce)`, `pass_challenge_url(base_url, challenge_id, response, nonce, redir, elapsed_ms=1000) -> str`, `error_reason(html, limit=200)`, and `AnubisError`.

- [ ] **Step 1: Copy anubis.py and its test into the relay**

```bash
mkdir -p relay/tests
cp resources/lib/csfd/anubis.py relay/anubis.py
cp tests/test_anubis.py relay/tests/test_anubis.py
```

- [ ] **Step 2: Fix the test import (relay modules are flat, not a package)**

Edit `relay/tests/test_anubis.py`: replace the import line
```python
from csfd import anubis
```
with
```python
import anubis
```

- [ ] **Step 3: Create `relay/pytest.ini`**

```ini
[pytest]
testpaths = tests
pythonpath = .
```

- [ ] **Step 4: Run the relay anubis tests**

Run: `cd relay && python -m pytest -q`
Expected: PASS (all tests from the relocated `test_anubis.py`, ~8 tests).

- [ ] **Step 5: Commit**

```bash
git add relay/anubis.py relay/pytest.ini relay/tests/test_anubis.py
git commit -m "feat(relay): add self-contained anubis module + tests"
```

---

### Task 2: Relay AnubisFetcher

The solver that runs on the relay: fetch a csfd page, solve Anubis if challenged (simple immediate submit — accepted on the relay's normal fingerprint), reuse the auth cookie via a long-lived session.

**Files:**
- Create: `relay/fetcher.py`
- Test: `relay/tests/test_fetcher.py`

**Interfaces:**
- Consumes: module `anubis` (Task 1).
- Produces: `class AnubisFetcher(min_interval=1.0, sleep=time.sleep, session=None, max_attempts=3)` with `get(url) -> str` (raises `anubis.AnubisError` if the wall can't be passed).

- [ ] **Step 1: Write the failing test**

Create `relay/tests/test_fetcher.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd relay && python -m pytest tests/test_fetcher.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'fetcher'`.

- [ ] **Step 3: Write the implementation**

Create `relay/fetcher.py`:
```python
import logging
import time

import requests

import anubis

log = logging.getLogger(__name__)

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

    def _throttle(self):
        if self._min_interval <= 0:
            return
        wait = self._min_interval - (time.time() - self._last_request)
        if wait > 0:
            self._sleep(wait)

    def _raw_get(self, url):
        self._throttle()
        resp = self._session.get(url, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        self._last_request = time.time()
        return resp.text

    def get(self, url):
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd relay && python -m pytest tests/test_fetcher.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add relay/fetcher.py relay/tests/test_fetcher.py
git commit -m "feat(relay): add AnubisFetcher (solve + reuse auth cookie)"
```

---

### Task 3: Relay HTTP app

Stdlib HTTP server exposing `/fetch` (SSRF-guarded) and `/health`, backed by one shared `AnubisFetcher`.

**Files:**
- Create: `relay/app.py`
- Test: `relay/tests/test_app.py`

**Interfaces:**
- Consumes: `AnubisFetcher` (Task 2), `anubis` (Task 1).
- Produces: `is_allowed_url(url) -> bool`, `make_handler(fetcher) -> BaseHTTPRequestHandler subclass`, `serve(port=None, fetcher=None)`.

- [ ] **Step 1: Write the failing test**

Create `relay/tests/test_app.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd relay && python -m pytest tests/test_app.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'app'`.

- [ ] **Step 3: Write the implementation**

Create `relay/app.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd relay && python -m pytest -q`
Expected: PASS (all relay tests: anubis + fetcher + app).

- [ ] **Step 5: Commit**

```bash
git add relay/app.py relay/tests/test_app.py
git commit -m "feat(relay): add http.server app with /fetch + /health"
```

---

### Task 4: Relay Docker packaging

Package the relay as an image and verify it runs.

**Files:**
- Create: `relay/requirements.txt`
- Create: `relay/Dockerfile`
- Create: `relay/docker-compose.yml`

- [ ] **Step 1: Create `relay/requirements.txt`**

```text
requests>=2.31.0
```

- [ ] **Step 2: Create `relay/Dockerfile`**

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY anubis.py fetcher.py app.py ./
ENV PORT=9753
EXPOSE 9753
CMD ["python", "app.py"]
```

- [ ] **Step 3: Create `relay/docker-compose.yml`**

```yaml
services:
  anubis-relay:
    image: bednic/anubis-relay:latest
    container_name: anubis-relay
    restart: unless-stopped
    ports:
      - "9753:9753"
    environment:
      - PORT=9753
```

- [ ] **Step 4: Build the image**

Run: `cd relay && docker build -t bednic/anubis-relay:latest .`
Expected: build succeeds, ends with `naming to docker.io/bednic/anubis-relay:latest`.

- [ ] **Step 5: Run the container and check health + a live fetch**

Run:
```bash
docker run -d --rm -p 9753:9753 --name anubis-relay-test bednic/anubis-relay:latest
sleep 2
curl -s http://127.0.0.1:9753/health
curl -s -o /dev/null -w "%{http_code}\n" "http://127.0.0.1:9753/fetch?url=https%3A%2F%2Fwww.csfd.cz%2Fhledat%2F%3Fq%3DMatrix"
docker stop anubis-relay-test
```
Expected: `/health` prints `ok`; the `/fetch` call prints `200` (relay solved Anubis and returned csfd HTML). If it prints `502`, inspect `docker logs anubis-relay-test` — a 502 means the relay host's own fingerprint is being challenged; that is out of scope for this task (the dev/NAS host should pass like the desktop did).

- [ ] **Step 6: Commit**

```bash
git add relay/requirements.txt relay/Dockerfile relay/docker-compose.yml
git commit -m "build(relay): Dockerfile + compose for bednic/anubis-relay"
```

---

### Task 5: Addon relay client + settings plumbing

Rewrite the addon client to fetch through the relay and remove all Anubis code, and — in the same task, since they share the `CsfdClient` signature — add `Settings.relay_url` and update `build_client`, so the suite stays green.

**Files:**
- Modify (rewrite): `resources/lib/csfd/client.py`
- Delete: `resources/lib/csfd/anubis.py`
- Modify (rewrite): `tests/test_client.py`
- Delete: `tests/test_anubis.py`
- Modify: `resources/lib/kodi/settings.py` (add `relay_url` property)
- Modify: `resources/lib/kodi/movie_scraper.py:14-17` (`build_client`)
- Test: `tests/test_settings.py` (create)

**Interfaces:**
- Consumes: nothing new (uses `requests` / injected session).
- Produces: `class CsfdClient(relay_url, cache_dir=None, ttl_seconds=604800, session=None)` with `get(url, ttl=None) -> str` (callers `csfd.search`/`csfd.film`/`csfd.episodes` already use `client.get(url[, ttl=...])`); `Settings.relay_url -> str`; `movie_scraper.build_client(settings) -> CsfdClient`.

- [ ] **Step 1: Rewrite `tests/test_client.py` and create `tests/test_settings.py` (failing)**

Replace the entire contents of `tests/test_client.py` with:
```python
import pytest
from csfd.client import CsfdClient


class FakeResponse:
    def __init__(self, text, status=200):
        self.text = text
        self.status_code = status
    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("HTTP %d" % self.status_code)


class FakeSession:
    def __init__(self, response=None):
        self.response = response or FakeResponse("<html>hi</html>")
        self.calls = []
    def get(self, url, headers=None, timeout=None):
        self.calls.append(url)
        return self.response


def test_get_fetches_via_relay_and_returns_body():
    s = FakeSession(FakeResponse("<html>page</html>"))
    c = CsfdClient("http://nas:9753", cache_dir=None, session=s)
    html = c.get("https://www.csfd.cz/film/1/")
    assert html == "<html>page</html>"
    assert s.calls == [
        "http://nas:9753/fetch?url=https%3A%2F%2Fwww.csfd.cz%2Ffilm%2F1%2F"]


def test_trailing_slash_in_relay_url_is_normalised():
    s = FakeSession()
    c = CsfdClient("http://nas:9753/", cache_dir=None, session=s)
    c.get("https://www.csfd.cz/x")
    assert s.calls[0].startswith("http://nas:9753/fetch?url=")


def test_cache_hit_avoids_second_relay_call(tmp_path):
    s = FakeSession(FakeResponse("<html>cached</html>"))
    c = CsfdClient("http://nas:9753", cache_dir=str(tmp_path), session=s)
    c.get("https://www.csfd.cz/film/1/")
    c.get("https://www.csfd.cz/film/1/")
    assert len(s.calls) == 1


def test_expired_cache_refetches(tmp_path):
    s = FakeSession(FakeResponse("<html>x</html>"))
    c = CsfdClient("http://nas:9753", cache_dir=str(tmp_path),
                   ttl_seconds=0, session=s)
    c.get("https://www.csfd.cz/film/1/")
    c.get("https://www.csfd.cz/film/1/")
    assert len(s.calls) == 2


def test_non_200_raises():
    s = FakeSession(FakeResponse("nope", status=502))
    c = CsfdClient("http://nas:9753", cache_dir=None, session=s)
    with pytest.raises(Exception):
        c.get("https://www.csfd.cz/film/1/")


def test_no_relay_url_raises():
    c = CsfdClient("", cache_dir=None, session=FakeSession())
    with pytest.raises(RuntimeError):
        c.get("https://www.csfd.cz/film/1/")
```

Create `tests/test_settings.py`:
```python
import xbmcaddon
from kodi.settings import Settings


def test_relay_url_reads_setting():
    xbmcaddon.Addon._settings = {"relay_url": "http://nas:9753"}
    assert Settings().relay_url == "http://nas:9753"


def test_relay_url_defaults_to_empty_when_unset():
    xbmcaddon.Addon._settings = {}
    assert Settings().relay_url == ""
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `python -m pytest tests/test_client.py tests/test_settings.py -q`
Expected: FAIL — old `CsfdClient` signature and no `Settings.relay_url`.

- [ ] **Step 3: Rewrite `resources/lib/csfd/client.py`**

Replace the entire contents with:
```python
import hashlib
import json
import logging
import os
import time
from urllib.parse import quote

log = logging.getLogger(__name__)


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
```

- [ ] **Step 4: Add `Settings.relay_url`**

In `resources/lib/kodi/settings.py`, add after the `debug` property:
```python
    @property
    def relay_url(self):
        return self._addon.getSettingString("relay_url")
```

- [ ] **Step 5: Update `build_client` to pass the relay URL**

In `resources/lib/kodi/movie_scraper.py`, replace the `build_client` function:
```python
def build_client(settings):
    return CsfdClient(settings.relay_url,
                      cache_dir=settings.profile_dir,
                      ttl_seconds=settings.cache_ttl_days * 86400)
```

- [ ] **Step 6: Delete the addon's Anubis module and its old test**

```bash
git rm resources/lib/csfd/anubis.py tests/test_anubis.py
```

- [ ] **Step 7: Run the full addon suite**

Run: `python -m pytest -q`
Expected: PASS. Nothing imports `csfd.anubis` any more (only the old `client.py` did); `build_client` now matches the new `CsfdClient` signature, so `test_movie_scraper` and `test_tv_mapping` stay green.

- [ ] **Step 8: Commit**

```bash
git add resources/lib/csfd/client.py tests/test_client.py tests/test_settings.py \
  resources/lib/kodi/settings.py resources/lib/kodi/movie_scraper.py
git commit -m "feat(addon): fetch via relay; drop on-device Anubis solving"
```

---

### Task 6: Addon settings UI + zip exclusion

Surface the `relay_url` setting in the addon UI and keep the relay out of the Kodi zip. Pure resources/config — no Python behavior change.

**Files:**
- Modify: `resources/settings.xml` (add setting `#30005`)
- Modify: `resources/language/resource.language.en_gb/strings.po`
- Modify: `resources/language/resource.language.cs_cz/strings.po`
- Modify: `.gitattributes` (add `relay/ export-ignore`)

- [ ] **Step 1: Add the setting to `resources/settings.xml`**

Insert, immediately after the closing `</setting>` of the `debug` setting and before `</group>`:
```xml
        <setting id="relay_url" type="string" label="30005">
          <level>0</level>
          <default>http://nas:9753</default>
          <control type="edit" format="string"/>
        </setting>
```

- [ ] **Step 2: Add string `#30005` to both `strings.po` files**

Append to `resources/language/resource.language.en_gb/strings.po`:
```
msgctxt "#30005"
msgid "Anubis relay URL"
msgstr ""
```
Append to `resources/language/resource.language.cs_cz/strings.po`:
```
msgctxt "#30005"
msgid "Anubis relay URL"
msgstr "URL Anubis relay"
```

- [ ] **Step 3: Keep the relay out of the addon zip**

Append to `.gitattributes`:
```
relay/           export-ignore
```

- [ ] **Step 4: Run the full addon suite (unaffected) and confirm the setting string id**

Run: `python -m pytest -q && grep -c '#30005' resources/language/resource.language.en_gb/strings.po && grep -c 'label="30005"' resources/settings.xml`
Expected: tests PASS; the `strings.po` grep prints `1` and the `settings.xml` grep prints `1`.

- [ ] **Step 5: Commit**

```bash
git add resources/settings.xml .gitattributes \
  resources/language/resource.language.en_gb/strings.po \
  resources/language/resource.language.cs_cz/strings.po
git commit -m "feat(addon): expose relay_url setting; exclude relay/ from zip"
```

---

### Task 7: Version bump, README, addon zip

Ship the addon as `0.2.0` and document the relay.

**Files:**
- Modify: `addon.xml:2` (version)
- Modify: `Makefile:1` (VERSION)
- Modify: `README.md`

- [ ] **Step 1: Bump the version in both places**

```bash
sed -i 's/version="0.1.9"/version="0.2.0"/' addon.xml
sed -i 's/VERSION := 0.1.9/VERSION := 0.2.0/' Makefile
grep -h 'version="0.2.0"\|VERSION := 0.2.0' addon.xml Makefile
```
Expected: both lines print with `0.2.0`.

- [ ] **Step 2: Document the relay in `README.md`**

Append this section to `README.md`:
```markdown
## Anubis relay (required)

csfd.cz is behind the Anubis bot wall, which blocks the Android TV / Kodi TLS
fingerprint. The addon therefore fetches pages through a small relay that runs
on a normal-fingerprint, always-on host (e.g. a NAS) and solves Anubis there.

### Run the relay (on the NAS)

```bash
# uses the published image bednic/anubis-relay
cd relay
docker compose up -d
curl -s http://localhost:9753/health   # -> ok
```

### Point the addon at it

In the addon settings, set **Anubis relay URL** to `http://<nas-host>:9753`
(default `http://nas:9753`). Without a reachable relay the addon cannot scrape.

### Build/push the image (maintainer)

```bash
cd relay
docker build -t bednic/anubis-relay:latest -t bednic/anubis-relay:0.2.0 .
docker push bednic/anubis-relay:latest
docker push bednic/anubis-relay:0.2.0
```
```

- [ ] **Step 3: Build the addon zip and verify version + no relay inside**

Run:
```bash
make zip
unzip -l build/metadata.csfd-0.2.0.zip | grep -E "addon.xml|relay/|docs/" || true
```
Expected: `metadata.csfd/addon.xml` present; **no** `relay/` or `docs/` entries.

- [ ] **Step 4: Commit**

```bash
git add addon.xml Makefile README.md
git commit -m "chore: release 0.2.0 (relay-based fetching) + README"
```

---

### Task 8: Publish the relay image to Docker Hub

Push `bednic/anubis-relay` from this already-logged-in machine. **Outward-facing publish — run only after Tasks 1–7 are green.**

- [ ] **Step 1: Build and tag**

Run: `cd relay && docker build -t bednic/anubis-relay:latest -t bednic/anubis-relay:0.2.0 .`
Expected: build succeeds.

- [ ] **Step 2: Push both tags**

Run:
```bash
docker push bednic/anubis-relay:latest
docker push bednic/anubis-relay:0.2.0
```
Expected: both pushes complete (`latest: digest: sha256:… size: …`). No login prompt (machine already `docker login`-ed).

- [ ] **Step 3: Verify the NAS can pull**

Run: `docker pull bednic/anubis-relay:0.2.0`
Expected: `Status: Downloaded newer image` (or `Image is up to date`).

No commit (publishing only; no repo changes).
