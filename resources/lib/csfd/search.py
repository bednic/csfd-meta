import logging
import re
from urllib.parse import quote

from bs4 import BeautifulSoup

from .models import SearchResult
from .urls import BASE_URL, absolute_url, film_id_from_url

log = logging.getLogger(__name__)
_YEAR_RE = re.compile(r"(\d{4})")


def _text(node):
    return node.get_text(strip=True) if node else None


def parse_search(html):
    soup = BeautifulSoup(html, "html.parser")
    results = []
    seen = set()
    # Verified: results are `a.film-title-name` anchors; each sits inside an
    # `.article` block that also holds a `.film-title-info` span with year/type.
    for link in soup.select("a.film-title-name"):
        href = link.get("href")
        if not href:
            continue
        url = absolute_url(href)
        # keep only top-level films/series; skip episode/season sub-results
        if len(re.findall(r"/\d+-[^/]+", url)) > 1:
            continue
        fid = film_id_from_url(url)
        if not fid or fid in seen:
            continue
        seen.add(fid)
        title = _text(link)
        art = link.find_parent(class_="article") or link.parent
        info = art.select_one(".film-title-info")
        year = None
        if info:
            m = _YEAR_RE.search(info.get_text())
            year = int(m.group(1)) if m else None
        type_text = (_text(info) or "").lower()
        is_series = any(w in type_text for w in ("seriál", "serial", "(série")) \
            or "/serie-" in url
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


def search(client, query):
    url = f"{BASE_URL}/hledat/?q={quote(query)}"
    html = client.get(url, ttl=86400)  # short TTL for searches
    return parse_search(html)
