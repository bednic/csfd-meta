# CSFD Kodi Metadata Scraper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a self-contained Kodi Omega (21) Python metadata scraper that pulls movie and TV-series metadata from CSFD.cz.

**Architecture:** A pure, Kodi-agnostic `csfd/` package (HTTP client + HTML parsers returning plain dataclasses) sits behind a thin Kodi glue layer (`kodi/`) that maps dataclasses onto Kodi's `InfoTagVideo`. The domain layer is fully unit-tested offline against saved HTML fixtures; the Kodi layer is tested with stubbed `xbmc*` modules.

**Tech Stack:** Python 3.11 (Kodi Omega), BeautifulSoup4, requests, pytest.

## Global Constraints

- **Target:** Kodi Omega 21 only. `addon.xml` requires `xbmc.python` version `3.0.1`.
- **Layer isolation:** files under `resources/lib/csfd/` MUST NOT import any `xbmc*` module. Only `resources/lib/kodi/` may touch Kodi APIs, and `mapping.py` is the only file that constructs Kodi `ListItem`/`InfoTagVideo`/`Actor` objects.
- **InfoTag API:** use Omega `ListItem.getVideoInfoTag()` setters (`setTitle`, `setPlot`, `setRatings`, `setCast`, `setUniqueIDs`, …). NEVER use the deprecated `ListItem.setInfo()`.
- **Dependencies (official Kodi-repo modules only, declared in `addon.xml`):** `script.module.requests`, `script.module.beautifulsoup4`, `script.module.certifi`. Nothing is vendored.
- **HTTP manners:** every outbound request sends a realistic browser `User-Agent`, `Accept-Language: cs`, the CSFD consent cookie, a ~10s timeout, and passes through the shared rate limiter.
- **Defensive parsing:** every field is extracted independently and wrapped so a missing/renamed element degrades that one field to `None`/empty (logged) and never aborts the scrape.
- **Selectors are provisional:** the CSS selectors in the parser tasks are a starting point. In each parser task you FIRST capture a real fixture, read the actual class names, then adjust selectors until the fixture tests (which assert values you read off the real page) pass. The tests are the source of truth, not the selectors printed here.
- **Base URL:** `https://www.csfd.cz`. All parsed relative URLs are resolved against it.
- **Commit style:** conventional commits (`feat:`, `test:`, `chore:`), one commit per task's final step.

---

## File Structure

```
csfd-meta/
├── addon.xml                          # Task 6
├── addon.py                           # Task 6
├── requirements-dev.txt              # Task 1
├── pytest.ini                         # Task 1
├── resources/
│   ├── settings.xml                   # Task 6
│   ├── language/
│   │   ├── resource.language.en_gb/strings.po   # Task 6
│   │   └── resource.language.cs_cz/strings.po   # Task 6
│   └── lib/
│       ├── __init__.py                # Task 1
│       ├── csfd/
│       │   ├── __init__.py            # Task 1
│       │   ├── models.py              # Task 1
│       │   ├── urls.py                # Task 1  (URL/ID normalization)
│       │   ├── client.py             # Task 2
│       │   ├── search.py             # Task 3
│       │   ├── film.py               # Task 4
│       │   └── episodes.py           # Task 5
│       └── kodi/
│           ├── __init__.py            # Task 6
│           ├── settings.py           # Task 6  (typed settings access)
│           ├── router.py             # Task 6
│           ├── mapping.py            # Task 7
│           ├── movie_scraper.py      # Task 7
│           └── tv_scraper.py         # Task 8
└── tests/
    ├── conftest.py                    # Task 1 (+ xbmc stubs added Task 6)
    ├── fixtures/                      # captured per parser task
    ├── stubs/                         # fake xbmc modules (Task 6)
    ├── test_urls.py                   # Task 1
    ├── test_client.py                # Task 2
    ├── test_search.py                # Task 3
    ├── test_film.py                  # Task 4
    ├── test_episodes.py              # Task 5
    ├── test_mapping.py               # Task 7
    └── test_canary.py                # Task 9 (network-marked)
```

---

## Task 1: Project scaffolding, domain models, URL normalization

**Files:**
- Create: `requirements-dev.txt`, `pytest.ini`
- Create: `resources/lib/__init__.py`, `resources/lib/csfd/__init__.py` (empty)
- Create: `resources/lib/csfd/models.py`
- Create: `resources/lib/csfd/urls.py`
- Create: `tests/conftest.py`
- Test: `tests/test_urls.py`

**Interfaces:**
- Produces: dataclasses `Person`, `Artwork`, `SearchResult`, `CsfdFilm`, `CsfdEpisode` (in `models.py`); functions `film_id_from_url(url) -> str | None`, `canonical_film_url(url) -> str`, `absolute_url(href) -> str`, and constant `BASE_URL` (in `urls.py`).

- [ ] **Step 1: Create dev dependency + pytest config files**

`requirements-dev.txt`:
```
requests>=2.31
beautifulsoup4>=4.12
pytest>=8.0
```

`pytest.ini`:
```ini
[pytest]
testpaths = tests
pythonpath = resources/lib
markers =
    network: hits the live CSFD site (deselected by default)
addopts = -m "not network"
```

- [ ] **Step 2: Create empty package markers and conftest**

Create empty `resources/lib/__init__.py` and `resources/lib/csfd/__init__.py`.

`tests/conftest.py`:
```python
import pathlib

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")
```

- [ ] **Step 3: Write the failing test for models + urls**

`tests/test_urls.py`:
```python
from csfd.urls import BASE_URL, film_id_from_url, canonical_film_url, absolute_url
from csfd import models


def test_film_id_extracted_from_full_url():
    assert film_id_from_url("https://www.csfd.cz/film/12345-matrix/") == "12345"


def test_film_id_extracted_from_episode_subpage():
    url = "https://www.csfd.cz/film/700-bratrstvo-neohrozenych/1000-epizoda/"
    assert film_id_from_url(url) == "700"


def test_film_id_none_for_non_film_url():
    assert film_id_from_url("https://www.csfd.cz/uzivatel/1-nekdo/") is None


def test_canonical_film_url_strips_slug_and_subpages():
    url = "https://www.csfd.cz/film/12345-matrix/prehled/"
    assert canonical_film_url(url) == "https://www.csfd.cz/film/12345/"


def test_absolute_url_resolves_relative_href():
    assert absolute_url("/film/1-x/") == f"{BASE_URL}/film/1-x/"


def test_absolute_url_passes_through_absolute():
    assert absolute_url("https://www.csfd.cz/film/1-x/") == "https://www.csfd.cz/film/1-x/"


def test_models_construct_with_defaults():
    f = models.CsfdFilm(csfd_id="1", url="u", title="T")
    assert f.genres == [] and f.cast == [] and f.rating is None
```

- [ ] **Step 4: Run test to verify it fails**

Run: `pytest tests/test_urls.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'csfd.urls'`

- [ ] **Step 5: Implement models.py**

`resources/lib/csfd/models.py`:
```python
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Person:
    name: str
    role: Optional[str] = None      # character name, for actors
    thumb: Optional[str] = None


@dataclass
class Artwork:
    url: str
    kind: str                        # "poster" | "fanart"


@dataclass
class SearchResult:
    csfd_id: str
    url: str
    title: str
    year: Optional[int] = None
    is_series: bool = False
    thumb: Optional[str] = None


@dataclass
class CsfdFilm:
    csfd_id: str
    url: str
    title: str
    original_title: Optional[str] = None
    year: Optional[int] = None
    plot: Optional[str] = None
    tagline: Optional[str] = None
    runtime: Optional[int] = None            # minutes
    countries: list = field(default_factory=list)
    genres: list = field(default_factory=list)
    rating: Optional[float] = None           # 0..10
    votes: Optional[int] = None
    cast: list = field(default_factory=list)          # list[Person]
    directors: list = field(default_factory=list)     # list[Person]
    writers: list = field(default_factory=list)       # list[Person]
    artwork: list = field(default_factory=list)       # list[Artwork]
    is_series: bool = False


@dataclass
class CsfdEpisode:
    csfd_id: str
    url: str
    title: str
    season: int
    episode: int
    plot: Optional[str] = None
    aired: Optional[str] = None              # ISO date "YYYY-MM-DD"
```

- [ ] **Step 6: Implement urls.py**

`resources/lib/csfd/urls.py`:
```python
import re
from urllib.parse import urljoin

BASE_URL = "https://www.csfd.cz"

_FILM_ID_RE = re.compile(r"/film/(\d+)")


def film_id_from_url(url: str) -> "str | None":
    if not url:
        return None
    m = _FILM_ID_RE.search(url)
    return m.group(1) if m else None


def canonical_film_url(url: str) -> str:
    fid = film_id_from_url(url)
    if fid is None:
        return url
    return f"{BASE_URL}/film/{fid}/"


def absolute_url(href: str) -> str:
    if not href:
        return href
    return urljoin(BASE_URL + "/", href)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/test_urls.py -v`
Expected: PASS (7 passed)

- [ ] **Step 8: Commit**

```bash
git add requirements-dev.txt pytest.ini resources/lib tests/conftest.py tests/test_urls.py
git commit -m "feat: add domain models, URL normalization, and test scaffolding"
```

---

## Task 2: HTTP client with consent cookie, caching, rate limiting

**Files:**
- Create: `resources/lib/csfd/client.py`
- Test: `tests/test_client.py`

**Interfaces:**
- Consumes: `BASE_URL` from `urls.py`.
- Produces: class `CsfdClient(cache_dir: str | None = None, ttl_seconds: int = 604800, min_interval: float = 1.0, sleep=time.sleep, session=None)` with method `get(url: str, ttl: int | None = None) -> str` returning page HTML (from cache when fresh). The `session` param accepts any object with a `.get(url, headers=, timeout=, cookies=)` returning an object with `.text` and `.raise_for_status()` — this is how tests inject a fake.

- [ ] **Step 1: Write the failing tests**

`tests/test_client.py`:
```python
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
    def get(self, url, headers=None, timeout=None, cookies=None):
        self.calls.append({"url": url, "headers": headers, "cookies": cookies})
        return FakeResponse(self.text)


def test_get_returns_html_and_sends_polite_headers():
    s = FakeSession("<html>hi</html>")
    c = CsfdClient(cache_dir=None, session=s, min_interval=0)
    html = c.get("https://www.csfd.cz/film/1/")
    assert html == "<html>hi</html>"
    hdrs = s.calls[0]["headers"]
    assert "Mozilla" in hdrs["User-Agent"]
    assert hdrs["Accept-Language"].startswith("cs")
    assert s.calls[0]["cookies"]  # consent cookie present


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'csfd.client'`

- [ ] **Step 3: Implement client.py**

`resources/lib/csfd/client.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_client.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add resources/lib/csfd/client.py tests/test_client.py
git commit -m "feat: add CSFD HTTP client with consent cookie, caching, rate limiting"
```

---

## Task 3: Search parser

**Files:**
- Create: `resources/lib/csfd/search.py`
- Create: `tests/fixtures/search.html` (captured)
- Test: `tests/test_search.py`

**Interfaces:**
- Consumes: `SearchResult` (models), `absolute_url`/`film_id_from_url` (urls), `CsfdClient.get` (client).
- Produces: `search(client, query: str, year: int | None = None) -> list[SearchResult]` and `parse_search(html: str) -> list[SearchResult]`.

- [ ] **Step 1: Capture the fixture**

Run (records a real search page; pick a well-known title):
```bash
python - <<'PY'
import urllib.request
req = urllib.request.Request(
    "https://www.csfd.cz/hledat/?q=matrix",
    headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "cs"})
html = urllib.request.urlopen(req).read().decode("utf-8")
open("tests/fixtures/search.html", "w", encoding="utf-8").write(html)
print(len(html), "bytes saved")
PY
```
Open `tests/fixtures/search.html`, find the movie-results block, and note the real class names and the first result's title/year/id. Use those real values in Step 2.

- [ ] **Step 2: Write the failing test** (replace the asserted values with what you read off the fixture)

`tests/test_search.py`:
```python
from conftest import load_fixture
from csfd.search import parse_search


def test_parse_search_returns_results():
    results = parse_search(load_fixture("search.html"))
    assert len(results) >= 1


def test_first_result_has_core_fields():
    r = parse_search(load_fixture("search.html"))[0]
    assert r.csfd_id.isdigit()
    assert r.url.startswith("https://www.csfd.cz/film/")
    assert r.title  # non-empty
    # Adjust the next two to the actual first result in your captured fixture:
    assert "Matrix" in r.title
    assert r.year == 1999


def test_series_flagged():
    results = parse_search(load_fixture("search.html"))
    assert all(isinstance(r.is_series, bool) for r in results)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_search.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'csfd.search'`

- [ ] **Step 4: Implement search.py** (adjust the selectors marked `# SELECTOR` to the fixture's real classes)

`resources/lib/csfd/search.py`:
```python
import logging
import re
from bs4 import BeautifulSoup

from .models import SearchResult
from .urls import absolute_url, film_id_from_url

log = logging.getLogger(__name__)
_YEAR_RE = re.compile(r"(\d{4})")


def _text(node):
    return node.get_text(strip=True) if node else None


def parse_search(html):
    soup = BeautifulSoup(html, "html.parser")
    results = []
    # SELECTOR: movie results container -> individual article rows.
    for art in soup.select("section.main-movies article, .search-results article"):
        link = art.select_one("a.film-title-name")  # SELECTOR
        if not link or not link.get("href"):
            continue
        url = absolute_url(link["href"])
        fid = film_id_from_url(url)
        if not fid:
            continue
        title = _text(link)
        year = None
        year_node = art.select_one(".film-title-info .info")  # SELECTOR
        if year_node:
            m = _YEAR_RE.search(year_node.get_text())
            year = int(m.group(1)) if m else None
        type_text = (_text(art.select_one(".film-title-info")) or "").lower()
        is_series = any(w in type_text for w in ("seriál", "serial"))
        thumb_node = art.select_one("img")
        thumb = None
        if thumb_node:
            thumb = thumb_node.get("src") or thumb_node.get("data-src")
            thumb = absolute_url(thumb) if thumb else None
        try:
            results.append(SearchResult(csfd_id=fid, url=url, title=title,
                                        year=year, is_series=is_series,
                                        thumb=thumb))
        except Exception:  # pragma: no cover - defensive
            log.warning("failed to build search result for %s", url)
    return results


def search(client, query, year=None):
    from urllib.parse import quote
    url = f"https://www.csfd.cz/hledat/?q={quote(query)}"
    html = client.get(url, ttl=86400)  # short TTL for searches
    return parse_search(html)
```

- [ ] **Step 5: Iterate selectors until tests pass**

Run: `pytest tests/test_search.py -v`
Adjust each `# SELECTOR` line against the real fixture markup until:
Expected: PASS (3 passed)

- [ ] **Step 6: Commit**

```bash
git add resources/lib/csfd/search.py tests/fixtures/search.html tests/test_search.py
git commit -m "feat: add CSFD search parser"
```

---

## Task 4: Film parser

**Files:**
- Create: `resources/lib/csfd/film.py`
- Create: `tests/fixtures/film.html` (captured)
- Test: `tests/test_film.py`

**Interfaces:**
- Consumes: `CsfdFilm`, `Person`, `Artwork` (models); `absolute_url`, `film_id_from_url`, `canonical_film_url` (urls); `CsfdClient.get`.
- Produces: `film(client, url: str, max_art: int = 5) -> CsfdFilm` and `parse_film(html: str, url: str, max_art: int = 5) -> CsfdFilm`.

- [ ] **Step 1: Capture the fixture**

```bash
python - <<'PY'
import urllib.request
req = urllib.request.Request(
    "https://www.csfd.cz/film/9499-matrix/",
    headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "cs"})
html = urllib.request.urlopen(req).read().decode("utf-8")
open("tests/fixtures/film.html", "w", encoding="utf-8").write(html)
print(len(html), "bytes saved")
PY
```
Read the page: note the Czech title, original title, year, rating %, a couple of genres, the director name, and the first-billed actor + character. Use those real values in Step 2.

- [ ] **Step 2: Write the failing test** (fill asserted values from the captured fixture)

`tests/test_film.py`:
```python
from conftest import load_fixture
from csfd.film import parse_film

URL = "https://www.csfd.cz/film/9499-matrix/"


def film():
    return parse_film(load_fixture("film.html"), URL)


def test_core_text():
    f = film()
    assert f.csfd_id == "9499"
    assert f.title  # e.g. "Matrix"
    assert f.year == 1999
    assert f.plot and len(f.plot) > 20
    assert "Akční" in f.genres or len(f.genres) >= 1


def test_rating_scaled_0_to_10():
    f = film()
    assert f.rating is not None
    assert 0.0 <= f.rating <= 10.0


def test_cast_and_crew():
    f = film()
    assert len(f.directors) >= 1
    assert len(f.cast) >= 1
    assert f.cast[0].name


def test_artwork_present_and_capped():
    f = film()
    assert any(a.kind == "poster" for a in f.artwork)
    assert len(f.artwork) <= 5
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_film.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'csfd.film'`

- [ ] **Step 4: Implement film.py** (adjust `# SELECTOR` lines to the fixture)

`resources/lib/csfd/film.py`:
```python
import logging
import re
from bs4 import BeautifulSoup

from .models import CsfdFilm, Person, Artwork
from .urls import absolute_url, canonical_film_url, film_id_from_url

log = logging.getLogger(__name__)
_INT_RE = re.compile(r"(\d+)")


def _text(node):
    return node.get_text(strip=True) if node else None


def _safe(fn, field):
    """Run an extractor, swallowing/logging any failure (defensive parsing)."""
    try:
        return fn()
    except Exception:
        log.warning("csfd film: failed to parse %s", field)
        return None


def _people(soup, header_words):
    """Extract a creator group whose <h4> label matches any header word."""
    out = []
    for group in soup.select(".creators h4, .film-creators h4"):  # SELECTOR
        label = group.get_text(strip=True).lower()
        if not any(w in label for w in header_words):
            continue
        container = group.parent
        for a in container.select("a[href*='/tvurce/']"):  # SELECTOR
            name = a.get_text(strip=True)
            if name:
                out.append(Person(name=name))
    return out


def parse_film(html, url, max_art=5):
    soup = BeautifulSoup(html, "html.parser")
    fid = film_id_from_url(url) or ""
    canonical = canonical_film_url(url)

    title = _safe(lambda: _text(soup.select_one(".film-header-name h1")), "title")  # SELECTOR

    def _orig():
        node = soup.select_one("ul.film-names li")  # SELECTOR
        return _text(node)
    original_title = _safe(_orig, "original_title")

    def _year():
        node = soup.select_one(".film-info-content .origin, .origin")  # SELECTOR
        m = re.search(r"(\d{4})", node.get_text()) if node else None
        return int(m.group(1)) if m else None
    year = _safe(_year, "year")

    def _plot():
        return _text(soup.select_one(".plot-full, .film-description p"))  # SELECTOR
    plot = _safe(_plot, "plot")

    def _genres():
        node = soup.select_one(".genres")  # SELECTOR
        if not node:
            return []
        return [g.strip() for g in node.get_text().split("/") if g.strip()]
    genres = _safe(_genres, "genres") or []

    def _rating():
        node = soup.select_one(".film-rating-average")  # SELECTOR
        if not node:
            return (None, None)
        m = _INT_RE.search(node.get_text())
        pct = int(m.group(1)) if m else None
        votes_node = soup.select_one(".rating-average-count, .ratings-btn")  # SELECTOR
        vm = _INT_RE.search(votes_node.get_text().replace("\xa0", "")) if votes_node else None
        votes = int(vm.group(1)) if vm else None
        return (round(pct / 10.0, 1) if pct is not None else None, votes)
    rating, votes = _safe(_rating, "rating") or (None, None)

    def _runtime():
        node = soup.select_one(".origin")  # SELECTOR
        if not node:
            return None
        m = re.search(r"(\d+)\s*min", node.get_text())
        return int(m.group(1)) if m else None
    runtime = _safe(_runtime, "runtime")

    def _countries():
        node = soup.select_one(".origin")  # SELECTOR
        if not node:
            return []
        first = node.get_text().split(",")[0]
        return [c.strip() for c in first.split("/") if c.strip() and not c.strip().isdigit()]
    countries = _safe(_countries, "countries") or []

    directors = _safe(lambda: _people(soup, ("režie", "rezie", "director")), "directors") or []
    writers = _safe(lambda: _people(soup, ("scénář", "scenar", "writer")), "writers") or []

    def _cast():
        people = []
        for a in soup.select(".creators a[href*='/tvurce/'], .film-cast a"):  # SELECTOR
            name = a.get_text(strip=True)
            if name:
                people.append(Person(name=name))
        return people
    cast = _safe(_cast, "cast") or []

    def _artwork():
        arts = []
        poster = soup.select_one(".film-posters img")  # SELECTOR
        if poster:
            src = poster.get("src") or poster.get("data-src")
            if src:
                arts.append(Artwork(url=absolute_url(src), kind="poster"))
        for img in soup.select(".gallery-item img")[: max_art - 1]:  # SELECTOR
            src = img.get("src") or img.get("data-src")
            if src:
                arts.append(Artwork(url=absolute_url(src), kind="fanart"))
        return arts[:max_art]
    artwork = _safe(_artwork, "artwork") or []

    is_series = bool(soup.select_one(".film-header .type-serial"))  # SELECTOR heuristic

    return CsfdFilm(
        csfd_id=fid, url=canonical, title=title or "",
        original_title=original_title, year=year, plot=plot,
        runtime=runtime, countries=countries, genres=genres,
        rating=rating, votes=votes, cast=cast, directors=directors,
        writers=writers, artwork=artwork, is_series=is_series,
    )


def film(client, url, max_art=5):
    html = client.get(url)
    return parse_film(html, url, max_art=max_art)
```

- [ ] **Step 5: Iterate selectors until tests pass**

Run: `pytest tests/test_film.py -v`
Adjust `# SELECTOR` lines against the fixture until:
Expected: PASS (4 passed)

- [ ] **Step 6: Commit**

```bash
git add resources/lib/csfd/film.py tests/fixtures/film.html tests/test_film.py
git commit -m "feat: add CSFD film/series detail parser"
```

---

## Task 5: Episode-list parser

**Files:**
- Create: `resources/lib/csfd/episodes.py`
- Create: `tests/fixtures/series_episodes.html` (captured)
- Test: `tests/test_episodes.py`

**Interfaces:**
- Consumes: `CsfdEpisode` (models); `absolute_url`, `film_id_from_url` (urls); `CsfdClient.get`.
- Produces: `episodes(client, series_url: str) -> list[CsfdEpisode]` and `parse_episodes(html: str) -> list[CsfdEpisode]`.

- [ ] **Step 1: Capture the fixture**

Pick a series with visible seasons/episodes. Find its episodes page (CSFD lists episodes under the series; capture the season overview page).
```bash
python - <<'PY'
import urllib.request
url = "https://www.csfd.cz/film/699784-bratrstvo-neohrozenych/prehled/"  # replace with a real series overview URL
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "cs"})
html = urllib.request.urlopen(req).read().decode("utf-8")
open("tests/fixtures/series_episodes.html", "w", encoding="utf-8").write(html)
print(len(html), "bytes saved")
PY
```
Note the real season/episode numbering scheme and the first episode's title so you can assert it.

- [ ] **Step 2: Write the failing test** (fill values from the fixture)

`tests/test_episodes.py`:
```python
from conftest import load_fixture
from csfd.episodes import parse_episodes


def test_returns_episodes():
    eps = parse_episodes(load_fixture("series_episodes.html"))
    assert len(eps) >= 1


def test_episode_has_numbering_and_title():
    ep = parse_episodes(load_fixture("series_episodes.html"))[0]
    assert ep.season >= 1
    assert ep.episode >= 1
    assert ep.title
    assert ep.url.startswith("https://www.csfd.cz/film/")
    assert ep.csfd_id.isdigit()


def test_no_duplicate_season_episode_pairs():
    eps = parse_episodes(load_fixture("series_episodes.html"))
    pairs = [(e.season, e.episode) for e in eps]
    assert len(pairs) == len(set(pairs))
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_episodes.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'csfd.episodes'`

- [ ] **Step 4: Implement episodes.py** (adjust `# SELECTOR` lines to the fixture)

`resources/lib/csfd/episodes.py`:
```python
import logging
import re
from bs4 import BeautifulSoup

from .models import CsfdEpisode
from .urls import absolute_url, film_id_from_url

log = logging.getLogger(__name__)
_SEASON_RE = re.compile(r"(\d+)\.\s*s[eé]zóna", re.IGNORECASE)
_EPISODE_RE = re.compile(r"\((\d+)\)|(\d+)\.\s*epizoda|E(\d+)", re.IGNORECASE)


def _ep_number(text):
    m = _EPISODE_RE.search(text or "")
    if not m:
        return None
    return int(next(g for g in m.groups() if g))


def parse_episodes(html):
    soup = BeautifulSoup(html, "html.parser")
    out = []
    season = 1
    # SELECTOR: iterate season blocks; each has a heading + a list of episode links.
    for block in soup.select(".film-episodes-list section, .episodes .season"):
        heading = block.select_one("h3, h4")  # SELECTOR
        if heading:
            sm = _SEASON_RE.search(heading.get_text())
            if sm:
                season = int(sm.group(1))
        ep_no = 0
        for link in block.select("a[href*='/film/']"):  # SELECTOR
            href = link.get("href")
            url = absolute_url(href)
            fid = film_id_from_url(url)
            if not fid:
                continue
            title = link.get_text(strip=True)
            parsed_no = _ep_number(title) or _ep_number(link.parent.get_text())
            ep_no = parsed_no if parsed_no else ep_no + 1
            out.append(CsfdEpisode(csfd_id=fid, url=url, title=title,
                                   season=season, episode=ep_no))
    # de-duplicate on (season, episode), keep first
    seen = set()
    unique = []
    for e in out:
        key = (e.season, e.episode)
        if key in seen:
            continue
        seen.add(key)
        unique.append(e)
    return unique


def episodes(client, series_url):
    html = client.get(series_url)
    return parse_episodes(html)
```

- [ ] **Step 5: Iterate selectors until tests pass**

Run: `pytest tests/test_episodes.py -v`
Adjust `# SELECTOR` lines against the fixture until:
Expected: PASS (3 passed)

- [ ] **Step 6: Commit**

```bash
git add resources/lib/csfd/episodes.py tests/fixtures/series_episodes.html tests/test_episodes.py
git commit -m "feat: add CSFD series episode-list parser"
```

---

## Task 6: Kodi addon skeleton, settings, router, xbmc test stubs

**Files:**
- Create: `addon.xml`, `addon.py`
- Create: `resources/settings.xml`
- Create: `resources/language/resource.language.en_gb/strings.po`
- Create: `resources/language/resource.language.cs_cz/strings.po`
- Create: `resources/lib/kodi/__init__.py`, `resources/lib/kodi/settings.py`, `resources/lib/kodi/router.py`
- Create: `tests/stubs/xbmc.py`, `tests/stubs/xbmcgui.py`, `tests/stubs/xbmcplugin.py`, `tests/stubs/xbmcaddon.py`, `tests/stubs/xbmcvfs.py`
- Modify: `tests/conftest.py` (register stubs on `sys.path`/`sys.modules`)
- Test: `tests/test_router.py`

**Interfaces:**
- Consumes: nothing from earlier Kodi tasks (first Kodi task).
- Produces: `route(handle: int, action: str, params: dict) -> None` (in `router.py`) dispatching to functions it will import from `movie_scraper`/`tv_scraper` (added in Tasks 7–8); `Settings` class (in `settings.py`) with properties `prefer_original_title: bool`, `cache_ttl_days: int`, `max_artwork: int`, `debug: bool`, and `profile_dir: str`.

- [ ] **Step 1: Create the xbmc test stubs**

`tests/stubs/xbmc.py`:
```python
class Actor:
    def __init__(self, name="", role="", order=-1, thumbnail=""):
        self.name, self.role, self.order, self.thumbnail = name, role, order, thumbnail

def log(msg, level=0):
    pass

LOGDEBUG = 0
LOGINFO = 1
LOGWARNING = 2
LOGERROR = 3
```

`tests/stubs/xbmcgui.py`:
```python
class _InfoTag:
    def __init__(self):
        self.data = {}
    def setTitle(self, v): self.data["title"] = v
    def setOriginalTitle(self, v): self.data["originaltitle"] = v
    def setPlot(self, v): self.data["plot"] = v
    def setTagline(self, v): self.data["tagline"] = v
    def setYear(self, v): self.data["year"] = v
    def setDuration(self, v): self.data["duration"] = v
    def setGenres(self, v): self.data["genres"] = v
    def setCountries(self, v): self.data["countries"] = v
    def setRatings(self, v, defaultrating=""): self.data["ratings"] = (v, defaultrating)
    def setUniqueIDs(self, v, defaultuniqueid=""): self.data["uniqueids"] = (v, defaultuniqueid)
    def setCast(self, v): self.data["cast"] = v
    def setDirectors(self, v): self.data["directors"] = v
    def setWriters(self, v): self.data["writers"] = v
    def setSeason(self, v): self.data["season"] = v
    def setEpisode(self, v): self.data["episode"] = v
    def setFirstAired(self, v): self.data["aired"] = v
    def setMediaType(self, v): self.data["mediatype"] = v

class ListItem:
    def __init__(self, label="", offscreen=False):
        self.label = label
        self._tag = _InfoTag()
        self.art = {}
        self.available_art = []
    def getVideoInfoTag(self): return self._tag
    def setArt(self, d): self.art.update(d)
    def addAvailableArtwork(self, url, art_type=""): self.available_art.append((url, art_type))
```

`tests/stubs/xbmcplugin.py`:
```python
_added = []
_resolved = []

def addDirectoryItem(handle, url, listitem, isFolder=False, totalItems=0):
    _added.append((handle, url, listitem, isFolder))
    return True

def addDirectoryItems(handle, items, totalItems=0):
    for url, li, folder in items:
        _added.append((handle, url, li, folder))
    return True

def setResolvedUrl(handle, succeeded, listitem):
    _resolved.append((handle, succeeded, listitem))

def endOfDirectory(handle, succeeded=True):
    pass

def reset():
    _added.clear()
    _resolved.clear()
```

`tests/stubs/xbmcaddon.py`:
```python
class Addon:
    _settings = {}
    def getSettingBool(self, k): return bool(self._settings.get(k, False))
    def getSettingInt(self, k): return int(self._settings.get(k, 0))
    def getSettingString(self, k): return str(self._settings.get(k, ""))
    def getAddonInfo(self, k): return "/tmp/csfd_profile" if k == "profile" else ""
```

`tests/stubs/xbmcvfs.py`:
```python
def translatePath(p): return p
def exists(p):
    import os
    return os.path.exists(p)
def mkdirs(p):
    import os
    os.makedirs(p, exist_ok=True)
    return True
```

- [ ] **Step 2: Register stubs in conftest and write the router test (failing)**

Append to `tests/conftest.py`:
```python
import sys
import pathlib as _pl

_STUBS = _pl.Path(__file__).parent / "stubs"
if str(_STUBS) not in sys.path:
    sys.path.insert(0, str(_STUBS))
```

`tests/test_router.py`:
```python
import xbmcplugin
from kodi.router import route


def test_unknown_action_does_not_raise():
    xbmcplugin.reset()
    route(1, "bogus", {})  # should be a no-op, not an exception


def test_find_action_dispatches(monkeypatch):
    called = {}
    import kodi.router as r
    monkeypatch.setattr(r, "movie_find",
                        lambda handle, params: called.setdefault("find", params))
    route(1, "find", {"title": "Matrix", "year": "1999"})
    assert called["find"] == {"title": "Matrix", "year": "1999"}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_router.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'kodi.router'`

- [ ] **Step 4: Implement settings.py and router.py**

Create empty `resources/lib/kodi/__init__.py`.

`resources/lib/kodi/settings.py`:
```python
import os
import xbmcaddon
import xbmcvfs


class Settings:
    def __init__(self):
        self._addon = xbmcaddon.Addon()

    @property
    def prefer_original_title(self):
        return self._addon.getSettingBool("prefer_original_title")

    @property
    def cache_ttl_days(self):
        return max(1, self._addon.getSettingInt("cache_ttl_days") or 7)

    @property
    def max_artwork(self):
        return max(1, self._addon.getSettingInt("max_artwork") or 5)

    @property
    def debug(self):
        return self._addon.getSettingBool("debug")

    @property
    def profile_dir(self):
        path = xbmcvfs.translatePath(self._addon.getAddonInfo("profile"))
        cache = os.path.join(path, "cache")
        if not xbmcvfs.exists(cache):
            xbmcvfs.mkdirs(cache)
        return cache
```

`resources/lib/kodi/router.py`:
```python
import logging

log = logging.getLogger(__name__)

# Imported lazily so the router module can be unit-tested and so that
# missing handlers during early bring-up don't break import.
from .movie_scraper import movie_find, movie_details, nfo_url          # noqa: E402
from .tv_scraper import (                                              # noqa: E402
    tv_find, tv_details, episode_list, episode_details,
)

_DISPATCH = {
    "find": lambda h, p: movie_find(h, p),
    "getdetails": lambda h, p: movie_details(h, p),
    "NfoUrl": lambda h, p: nfo_url(h, p),
    "getepisodelist": lambda h, p: episode_list(h, p),
    "getepisodedetails": lambda h, p: episode_details(h, p),
}


def route(handle, action, params):
    # For TV content Kodi calls find/getdetails too; movie_* and tv_* share
    # the same search/detail code path via the mapping layer, so a single
    # find/getdetails entry serves both. See Task 8.
    handler = _DISPATCH.get(action)
    if handler is None:
        log.warning("csfd: unknown action %r", action)
        return
    try:
        handler(handle, params)
    except Exception:
        log.exception("csfd: action %r failed", action)
```

> Note for Step 2's `monkeypatch.setattr(r, "movie_find", ...)`: because `route` calls `movie_find` through the `_DISPATCH` lambda which resolves `movie_find` at call time from module globals, patching `r.movie_find` takes effect. Keep the lambdas referencing the bare names.

- [ ] **Step 5: Create addon.xml, addon.py, settings.xml, language files**

`addon.xml`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<addon id="metadata.csfd" name="CSFD" version="0.1.0" provider-name="Tomas Benedikt">
  <requires>
    <import addon="xbmc.python" version="3.0.1"/>
    <import addon="xbmc.metadata" version="2.1.0"/>
    <import addon="script.module.requests" version="2.31.0"/>
    <import addon="script.module.beautifulsoup4" version="4.12.2"/>
    <import addon="script.module.certifi" version="2023.7.22"/>
  </requires>
  <extension point="xbmc.metadata.scraper.movies" library="addon.py" language="cz"/>
  <extension point="xbmc.metadata.scraper.tvshows" library="addon.py" language="cz"/>
  <extension point="xbmc.addon.metadata">
    <summary lang="en_gb">CSFD.cz metadata scraper</summary>
    <summary lang="cs_cz">Stahovač metadat z CSFD.cz</summary>
    <description lang="en_gb">Scrapes movie and TV series metadata from CSFD.cz.</description>
    <platform>all</platform>
    <license>MIT</license>
    <assets/>
  </extension>
</addon>
```

`addon.py`:
```python
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "resources", "lib"))

from urllib.parse import parse_qs  # noqa: E402
from kodi.router import route      # noqa: E402


def _parse_params(argv):
    # Kodi passes the action query on argv[1] (leading '?') and handle on argv[0]... varies;
    # metadata scrapers receive the request as a plugin path. Normalize both forms.
    handle = int(argv[1]) if len(argv) > 1 and argv[1].lstrip("-").isdigit() else -1
    query = ""
    for a in argv:
        if a.startswith("?") or "action=" in a:
            query = a.lstrip("?")
            break
    raw = parse_qs(query)
    params = {k: v[0] for k, v in raw.items()}
    return handle, params


if __name__ == "__main__":
    handle, params = _parse_params(sys.argv)
    action = params.get("action", "")
    route(handle, action, params)
```

`resources/settings.xml` (Omega format):
```xml
<?xml version="1.0" encoding="utf-8"?>
<settings version="1">
  <section id="metadata.csfd">
    <category id="general" label="30000">
      <group id="1">
        <setting id="prefer_original_title" type="boolean" label="30001">
          <level>0</level>
          <default>false</default>
          <control type="toggle"/>
        </setting>
        <setting id="max_artwork" type="integer" label="30002">
          <level>0</level>
          <default>5</default>
          <constraints><minimum>1</minimum><maximum>20</maximum></constraints>
          <control type="slider" format="integer"/>
        </setting>
        <setting id="cache_ttl_days" type="integer" label="30003">
          <level>0</level>
          <default>7</default>
          <constraints><minimum>1</minimum><maximum>90</maximum></constraints>
          <control type="slider" format="integer"/>
        </setting>
        <setting id="debug" type="boolean" label="30004">
          <level>0</level>
          <default>false</default>
          <control type="toggle"/>
        </setting>
      </group>
    </category>
  </section>
</settings>
```

`resources/language/resource.language.en_gb/strings.po`:
```po
msgid ""
msgstr "Content-Type: text/plain; charset=UTF-8\n"

msgctxt "#30000"
msgid "General"
msgstr ""

msgctxt "#30001"
msgid "Prefer original title as display title"
msgstr ""

msgctxt "#30002"
msgid "Maximum artwork per type"
msgstr ""

msgctxt "#30003"
msgid "Cache lifetime (days)"
msgstr ""

msgctxt "#30004"
msgid "Enable debug logging"
msgstr ""
```

`resources/language/resource.language.cs_cz/strings.po`:
```po
msgid ""
msgstr "Content-Type: text/plain; charset=UTF-8\n"

msgctxt "#30000"
msgid "General"
msgstr "Obecné"

msgctxt "#30001"
msgid "Prefer original title as display title"
msgstr "Upřednostnit původní název jako zobrazovaný"

msgctxt "#30002"
msgid "Maximum artwork per type"
msgstr "Maximální počet obrázků na typ"

msgctxt "#30003"
msgid "Cache lifetime (days)"
msgstr "Doba platnosti mezipaměti (dny)"

msgctxt "#30004"
msgid "Enable debug logging"
msgstr "Zapnout ladicí protokolování"
```

- [ ] **Step 6: Run router test to verify it passes**

Run: `pytest tests/test_router.py -v`
Expected: PASS (2 passed)

> If `route`'s top-level import of `movie_scraper`/`tv_scraper` fails because those modules don't exist yet, create them now as **temporary stubs** so this task's deliverable (a routable skeleton) is testable. Tasks 7–8 replace the bodies:
> `resources/lib/kodi/movie_scraper.py` → `def movie_find(h,p): pass` / `def movie_details(h,p): pass` / `def nfo_url(h,p): pass`
> `resources/lib/kodi/tv_scraper.py` → `def tv_find(h,p): pass` / `def tv_details(h,p): pass` / `def episode_list(h,p): pass` / `def episode_details(h,p): pass`

- [ ] **Step 7: Commit**

```bash
git add addon.xml addon.py resources/settings.xml resources/language resources/lib/kodi tests/stubs tests/conftest.py tests/test_router.py
git commit -m "feat: add Kodi addon skeleton, settings, router, and xbmc test stubs"
```

---

## Task 7: Mapping layer + movie scraper glue

**Files:**
- Create/replace: `resources/lib/kodi/mapping.py`, `resources/lib/kodi/movie_scraper.py`
- Test: `tests/test_mapping.py`

**Interfaces:**
- Consumes: `CsfdFilm`, `Person` (models); `Settings` (settings); `xbmcgui`, `xbmcplugin`, `xbmc` (stubbed in tests).
- Produces: `film_to_listitem(film: CsfdFilm, prefer_original: bool, media_type: str = "movie") -> xbmcgui.ListItem` (mapping.py); `movie_find(handle, params)`, `movie_details(handle, params)`, `nfo_url(handle, params)` (movie_scraper.py); helper `build_client(settings) -> CsfdClient`.

- [ ] **Step 1: Write the failing mapping test**

`tests/test_mapping.py`:
```python
import xbmcgui
from csfd.models import CsfdFilm, Person, Artwork
from kodi.mapping import film_to_listitem


def sample():
    return CsfdFilm(
        csfd_id="9499", url="https://www.csfd.cz/film/9499/", title="Matrix",
        original_title="The Matrix", year=1999, plot="A hacker...",
        runtime=136, countries=["USA"], genres=["Akční", "Sci-Fi"],
        rating=8.6, votes=120000,
        cast=[Person(name="Keanu Reeves", role="Neo")],
        directors=[Person(name="Lana Wachowski")],
        writers=[Person(name="Lilly Wachowski")],
        artwork=[Artwork(url="http://img/p.jpg", kind="poster"),
                 Artwork(url="http://img/f.jpg", kind="fanart")],
    )


def test_maps_core_fields_and_rating():
    li = film_to_listitem(sample(), prefer_original=False)
    tag = li.getVideoInfoTag().data
    assert tag["title"] == "Matrix"
    assert tag["originaltitle"] == "The Matrix"
    assert tag["year"] == 1999
    assert tag["duration"] == 136 * 60
    assert tag["genres"] == ["Akční", "Sci-Fi"]
    assert tag["ratings"][0]["csfd"] == (8.6, 120000)
    assert tag["ratings"][1] == "csfd"
    assert tag["uniqueids"] == ({"csfd": "9499"}, "csfd")


def test_prefer_original_swaps_display_title():
    li = film_to_listitem(sample(), prefer_original=True)
    tag = li.getVideoInfoTag().data
    assert tag["title"] == "The Matrix"
    assert tag["originaltitle"] == "The Matrix"


def test_cast_and_art_mapped():
    li = film_to_listitem(sample(), prefer_original=False)
    tag = li.getVideoInfoTag().data
    assert tag["cast"][0].name == "Keanu Reeves"
    assert tag["cast"][0].role == "Neo"
    assert li.art["poster"] == "http://img/p.jpg"
    assert li.art["fanart"] == "http://img/f.jpg"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_mapping.py -v`
Expected: FAIL with `ImportError: cannot import name 'film_to_listitem'`

- [ ] **Step 3: Implement mapping.py**

`resources/lib/kodi/mapping.py`:
```python
import xbmc
import xbmcgui


def _actors(people):
    actors = []
    for i, p in enumerate(people):
        actors.append(xbmc.Actor(p.name, p.role or "", i, p.thumb or ""))
    return actors


def film_to_listitem(film, prefer_original, media_type="movie"):
    display = film.title
    if prefer_original and film.original_title:
        display = film.original_title
    li = xbmcgui.ListItem(display, offscreen=True)
    tag = li.getVideoInfoTag()
    tag.setMediaType(media_type)
    tag.setTitle(display)
    if film.original_title:
        tag.setOriginalTitle(film.original_title)
    if film.plot:
        tag.setPlot(film.plot)
    if film.tagline:
        tag.setTagline(film.tagline)
    if film.year:
        tag.setYear(film.year)
    if film.runtime:
        tag.setDuration(film.runtime * 60)
    if film.genres:
        tag.setGenres(film.genres)
    if film.countries:
        tag.setCountries(film.countries)
    if film.rating is not None:
        tag.setRatings({"csfd": (film.rating, film.votes or 0)},
                       defaultrating="csfd")
    tag.setUniqueIDs({"csfd": film.csfd_id}, defaultuniqueid="csfd")
    if film.cast:
        tag.setCast(_actors(film.cast))
    if film.directors:
        tag.setDirectors([p.name for p in film.directors])
    if film.writers:
        tag.setWriters([p.name for p in film.writers])
    art = {}
    for a in film.artwork:
        art.setdefault(a.kind, a.url)
        li.addAvailableArtwork(a.url, a.kind)
    if art:
        li.setArt(art)
    return li
```

> The stub `_InfoTag.setRatings` stores `(v, defaultrating)`; the test reads `tag["ratings"][0]["csfd"]` and `tag["ratings"][1]`. This matches the stub in Task 6.

- [ ] **Step 4: Run mapping test to verify it passes**

Run: `pytest tests/test_mapping.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Implement movie_scraper.py**

`resources/lib/kodi/movie_scraper.py`:
```python
import logging

import xbmcgui
import xbmcplugin

from csfd.client import CsfdClient
from csfd.urls import absolute_url, film_id_from_url
from csfd import search as csfd_search
from csfd import film as csfd_film
from .mapping import film_to_listitem
from .settings import Settings

log = logging.getLogger(__name__)


def build_client(settings):
    return CsfdClient(cache_dir=settings.profile_dir,
                      ttl_seconds=settings.cache_ttl_days * 86400,
                      min_interval=1.0)


def movie_find(handle, params):
    settings = Settings()
    client = build_client(settings)
    title = params.get("title", "")
    year = params.get("year")
    results = csfd_search.search(client, title)
    if year and year.isdigit():
        y = int(year)
        results.sort(key=lambda r: 0 if r.year == y else 1)
    for r in results:
        li = xbmcgui.ListItem(r.title, offscreen=True)
        li.getVideoInfoTag().setUniqueIDs({"csfd": r.csfd_id}, "csfd")
        if r.year:
            li.getVideoInfoTag().setYear(r.year)
        if r.thumb:
            li.setArt({"thumb": r.thumb})
        xbmcplugin.addDirectoryItem(handle=handle, url=r.url, listitem=li,
                                    isFolder=True)
    xbmcplugin.endOfDirectory(handle)


def movie_details(handle, params):
    settings = Settings()
    client = build_client(settings)
    url = params.get("url", "")
    f = csfd_film.film(client, url, max_art=settings.max_artwork)
    li = film_to_listitem(f, settings.prefer_original_title, media_type="movie")
    xbmcplugin.setResolvedUrl(handle, True, li)


def nfo_url(handle, params):
    nfo = params.get("nfo", "")
    fid = film_id_from_url(nfo)
    if not fid:
        return
    url = absolute_url(f"/film/{fid}/")
    li = xbmcgui.ListItem(url, offscreen=True)
    xbmcplugin.addDirectoryItem(handle=handle, url=url, listitem=li,
                                isFolder=True)
    xbmcplugin.endOfDirectory(handle)
```

- [ ] **Step 6: Run the full suite**

Run: `pytest -v`
Expected: PASS (all tests from Tasks 1–7 green)

- [ ] **Step 7: Commit**

```bash
git add resources/lib/kodi/mapping.py resources/lib/kodi/movie_scraper.py tests/test_mapping.py
git commit -m "feat: add InfoTag mapping and movie scraper glue"
```

---

## Task 8: TV scraper glue

**Files:**
- Replace: `resources/lib/kodi/tv_scraper.py`
- Modify: `resources/lib/kodi/mapping.py` (add `episode_to_listitem`)
- Test: `tests/test_tv_mapping.py`

**Interfaces:**
- Consumes: `CsfdEpisode` (models); `episodes()` (csfd.episodes); `film()` (csfd.film); `film_to_listitem` (mapping); `build_client` (movie_scraper); `Settings`.
- Produces: `tv_find(handle, params)`, `tv_details(handle, params)`, `episode_list(handle, params)`, `episode_details(handle, params)` (tv_scraper.py); `episode_to_listitem(ep: CsfdEpisode) -> xbmcgui.ListItem` (mapping.py).

- [ ] **Step 1: Write the failing episode-mapping test**

`tests/test_tv_mapping.py`:
```python
from csfd.models import CsfdEpisode
from kodi.mapping import episode_to_listitem


def test_episode_maps_numbering_and_title():
    ep = CsfdEpisode(csfd_id="500", url="u", title="Pilot",
                     season=1, episode=1, aired="2001-09-23")
    li = episode_to_listitem(ep)
    tag = li.getVideoInfoTag().data
    assert tag["title"] == "Pilot"
    assert tag["season"] == 1
    assert tag["episode"] == 1
    assert tag["aired"] == "2001-09-23"
    assert tag["mediatype"] == "episode"
    assert tag["uniqueids"] == ({"csfd": "500"}, "csfd")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tv_mapping.py -v`
Expected: FAIL with `ImportError: cannot import name 'episode_to_listitem'`

- [ ] **Step 3: Add episode_to_listitem to mapping.py**

Append to `resources/lib/kodi/mapping.py`:
```python
def episode_to_listitem(ep):
    li = xbmcgui.ListItem(ep.title, offscreen=True)
    tag = li.getVideoInfoTag()
    tag.setMediaType("episode")
    tag.setTitle(ep.title)
    tag.setSeason(ep.season)
    tag.setEpisode(ep.episode)
    if ep.plot:
        tag.setPlot(ep.plot)
    if ep.aired:
        tag.setFirstAired(ep.aired)
    tag.setUniqueIDs({"csfd": ep.csfd_id}, defaultuniqueid="csfd")
    return li
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tv_mapping.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Implement tv_scraper.py**

`resources/lib/kodi/tv_scraper.py`:
```python
import logging

import xbmcgui
import xbmcplugin

from csfd import episodes as csfd_episodes
from csfd import film as csfd_film
from .mapping import film_to_listitem, episode_to_listitem
from .movie_scraper import build_client
from .settings import Settings

log = logging.getLogger(__name__)


def tv_find(handle, params):
    # Show search reuses the movie find path (same CSFD search page).
    from .movie_scraper import movie_find
    movie_find(handle, params)


def tv_details(handle, params):
    settings = Settings()
    client = build_client(settings)
    url = params.get("url", "")
    f = csfd_film.film(client, url, max_art=settings.max_artwork)
    li = film_to_listitem(f, settings.prefer_original_title, media_type="tvshow")
    xbmcplugin.setResolvedUrl(handle, True, li)


def episode_list(handle, params):
    settings = Settings()
    client = build_client(settings)
    url = params.get("url", "")
    for ep in csfd_episodes.episodes(client, url):
        li = xbmcgui.ListItem(ep.title, offscreen=True)
        tag = li.getVideoInfoTag()
        tag.setTitle(ep.title)
        tag.setSeason(ep.season)
        tag.setEpisode(ep.episode)
        xbmcplugin.addDirectoryItem(handle=handle, url=ep.url, listitem=li,
                                    isFolder=True)
    xbmcplugin.endOfDirectory(handle)


def episode_details(handle, params):
    settings = Settings()
    client = build_client(settings)
    url = params.get("url", "")
    # v1 scope: minimal per-episode detail. Reuse the film parser for the
    # episode sub-page; fall back to title only if fields are absent.
    f = csfd_film.film(client, url, max_art=1)
    from csfd.models import CsfdEpisode
    season = int(params.get("season", "1") or 1)
    number = int(params.get("episode", "1") or 1)
    ep = CsfdEpisode(csfd_id=f.csfd_id, url=f.url, title=f.title or "",
                     season=season, episode=number, plot=f.plot)
    li = episode_to_listitem(ep)
    xbmcplugin.setResolvedUrl(handle, True, li)
```

- [ ] **Step 6: Wire show find/getdetails into the router**

The scanner uses the same `find`/`getdetails` actions for TV as for movies, but the TV scraper needs `tvshow` media type. Update `resources/lib/kodi/router.py` `_DISPATCH` so `getdetails` chooses by a `mediatype`/content hint param when present, defaulting to movie:

Replace the `getdetails` entry in `_DISPATCH`:
```python
from .tv_scraper import tv_find, tv_details, episode_list, episode_details  # noqa: E402

def _details(handle, params):
    if (params.get("mediatype") == "tvshow"
            or params.get("content") == "tvshows"):
        return tv_details(handle, params)
    return movie_details(handle, params)

_DISPATCH["getdetails"] = _details
```

Run: `pytest -v`
Expected: PASS (all tests green)

- [ ] **Step 7: Commit**

```bash
git add resources/lib/kodi/tv_scraper.py resources/lib/kodi/mapping.py resources/lib/kodi/router.py tests/test_tv_mapping.py
git commit -m "feat: add TV show and episode scraper glue"
```

---

## Task 9: Live canary test, README, packaging

**Files:**
- Create: `tests/test_canary.py`
- Create: `README.md`
- Create: `Makefile` (or `scripts/package.sh`)

**Interfaces:**
- Consumes: `CsfdClient`, `search`, `film`, `episodes`.
- Produces: a `zip` build artifact `metadata.csfd-0.1.0.zip`.

- [ ] **Step 1: Write the network-marked canary test**

`tests/test_canary.py`:
```python
import pytest

pytestmark = pytest.mark.network


@pytest.fixture(scope="module")
def client():
    from csfd.client import CsfdClient
    return CsfdClient(cache_dir=None, min_interval=1.0)


def test_search_live(client):
    from csfd.search import search
    results = search(client, "Matrix")
    assert len(results) >= 1
    assert results[0].csfd_id.isdigit()


def test_film_live(client):
    from csfd.film import film
    f = film(client, "https://www.csfd.cz/film/9499-matrix/")
    assert f.title
    assert f.rating is not None
    assert len(f.directors) >= 1
    assert len(f.cast) >= 1
    assert any(a.kind == "poster" for a in f.artwork)
```

- [ ] **Step 2: Run the canary against the live site**

Run: `pytest tests/test_canary.py -m network -v`
Expected: PASS (2 passed). If it FAILS, CSFD's layout has drifted — re-capture the affected fixture (Tasks 3–5, Step 1) and fix the selectors. This is the intended early-warning behavior.

- [ ] **Step 3: Verify the default suite still excludes network tests**

Run: `pytest -v`
Expected: canary tests are deselected (only offline tests run and pass).

- [ ] **Step 4: Write README.md**

`README.md`:
```markdown
# CSFD Kodi Metadata Scraper (metadata.csfd)

Scrapes movie and TV-series metadata from [CSFD.cz](https://www.csfd.cz) for
Kodi **Omega (21)**.

## Features
- Movies and TV series (show-level metadata + episode titles/numbering)
- Core text, CSFD rating (as 0–10), cast & crew, poster/fanart artwork
- Configurable display-title language (Czech default, original optional)
- Disk caching + polite rate limiting

## Install
Build the zip and install it in Kodi via *Add-ons → Install from zip file*:

    make zip

Then set CSFD as the information provider for your Movies / TV Shows sources.

## Development
    python -m pip install -r requirements-dev.txt
    pytest                 # offline unit tests (fixtures)
    pytest -m network      # live canary tests (hit CSFD)

When CSFD changes layout, a canary test fails: re-capture the relevant
fixture under `tests/fixtures/` and update the selectors until green.
```

- [ ] **Step 5: Write the packaging target**

`Makefile`:
```makefile
VERSION := 0.1.0
NAME := metadata.csfd

.PHONY: test zip clean
test:
	pytest

zip:
	rm -f $(NAME)-$(VERSION).zip
	cd .. && zip -r csfd-meta/$(NAME)-$(VERSION).zip csfd-meta \
		-x 'csfd-meta/.git/*' 'csfd-meta/tests/*' 'csfd-meta/.idea/*' \
		'csfd-meta/docs/*' 'csfd-meta/*.zip' 'csfd-meta/requirements-dev.txt' \
		'csfd-meta/pytest.ini' 'csfd-meta/Makefile'

clean:
	rm -f $(NAME)-$(VERSION).zip
```

> Note: Kodi expects the addon id (`metadata.csfd`) as the top folder inside the zip. If your working dir is named `csfd-meta`, either rename it to `metadata.csfd` before zipping or adjust the `zip` rule to stage the files under a `metadata.csfd/` directory. Verify by opening the built zip.

- [ ] **Step 6: Build and verify the zip**

Run: `make zip && unzip -l metadata.csfd-0.1.0.zip | head -30`
Expected: archive lists `metadata.csfd/addon.xml`, `addon.py`, `resources/...` and does NOT contain `tests/`, `.git/`, or `docs/`.

- [ ] **Step 7: Commit**

```bash
git add tests/test_canary.py README.md Makefile
git commit -m "feat: add live canary tests, README, and packaging"
```

---

## Manual verification in Kodi (post-implementation)

Automated tests cover parsing and mapping; the scanner integration must be
checked by hand once:

1. Install `metadata.csfd-0.1.0.zip` in a Kodi Omega instance.
2. Create a Movies source, set its information provider to **CSFD**, scan a
   folder with a couple of well-known films → verify title, year, plot, rating,
   cast, poster/fanart populate.
3. Toggle *Prefer original title* in the addon settings, refresh a movie →
   verify the display title switches.
4. Create a TV Shows source, set provider to CSFD, scan a series → verify the
   show scrapes and episodes match by season/episode.
5. Check `kodi.log` for warnings from defensive parsing on any field that
   didn't populate; if a field is consistently empty, capture that page as a
   fixture and fix the selector.
```

---

## Self-Review

**1. Spec coverage:**
- Omega 21 native Python scraper (2 extension points) → Task 6 `addon.xml`. ✓
- Self-contained, backend-ready isolation (`csfd/` no Kodi imports) → Global Constraints + Tasks 1–5 pure; enforced by offline tests. ✓
- Core text / ratings / cast&crew / artwork → Task 4 parser + Task 7 mapping. ✓
- TV show-level + episode titles → Tasks 5, 8. ✓
- Configurable title language → Task 6 setting + Task 7 `prefer_original`. ✓
- BeautifulSoup4 → Tasks 3–5. ✓
- Client: consent cookie, caching, rate-limit → Task 2. ✓
- Defensive parsing → `_safe` in Task 4; try/except in search/episodes. ✓
- Fixture tests + live canary → Tasks 3–5 + Task 9. ✓
- Settings (title, trailers stub, TTL, max art, debug) → Task 6. *Note:* trailers stub omitted from settings.xml to honor YAGNI; deferred cleanly per spec "out of scope". ✓ (documented deviation)
- Dependencies (requests, bs4, certifi) → Task 6 `addon.xml`. ✓
- Distribution zip → Task 9. ✓
- Build order 1–8 → Tasks 1–9 mirror it. ✓

**2. Placeholder scan:** No "TBD"/"implement later". Selector `# SELECTOR` markers are intentional and paired with a fixture-capture + iterate-until-green loop, not placeholders. Temporary stubs in Task 6 are explicitly replaced in Tasks 7–8.

**3. Type consistency:** `film()`/`parse_film`, `search()`/`parse_search`, `episodes()`/`parse_episodes`, `film_to_listitem`, `episode_to_listitem`, `build_client`, `Settings` properties, and the `_DISPATCH` handler names are used consistently across tasks and match the stub method names defined in Task 6.
