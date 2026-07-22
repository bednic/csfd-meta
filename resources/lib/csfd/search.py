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


def _build_result(link, is_series, seen):
    href = link.get("href")
    if not href:
        return None
    url = absolute_url(href)
    # keep only top-level films/series; skip episode/season sub-results
    if len(re.findall(r"/\d+-[^/]+", url)) > 1:
        return None
    fid = film_id_from_url(url)
    if not fid or fid in seen:
        return None
    seen.add(fid)
    title = _text(link)
    art = link.find_parent(class_="article") or link.parent
    info = art.select_one(".film-title-info")
    year = None
    if info:
        m = _YEAR_RE.search(info.get_text())
        year = int(m.group(1)) if m else None
    thumb_node = art.select_one("img")
    thumb = None
    if thumb_node:
        thumb = thumb_node.get("src") or thumb_node.get("data-src")
        thumb = absolute_url(thumb) if thumb else None
    try:
        return SearchResult(csfd_id=fid, url=url, title=title, year=year,
                            is_series=is_series, thumb=thumb)
    except Exception:  # pragma: no cover - defensive
        log.warning("failed to build search result for %s", url)
        return None


def parse_search(html):
    soup = BeautifulSoup(html, "html.parser")
    results = []
    seen = set()
    # CSFD's search page splits hits into a "Filmy" (#films) and a "Seriály"
    # (#series) section. Trust that categorization to decide is_series rather
    # than parsing the type label: many series ("minisérie", "TV pořad", …)
    # never contain the literal word "seriál" and would otherwise be misfiled
    # as movies and vanish from Kodi's TV results. Process #films first so the
    # top movie result stays first. Results inside `a.film-title-name` anchors,
    # each in an `.article` block with a `.film-title-info` year/type span.
    sections = [
        ('section[data-search-results="films"], section#films', False),
        ('section[data-search-results="series"], section#series', True),
    ]
    for selector, is_series in sections:
        section = soup.select_one(selector)
        if not section:
            continue
        for link in section.select("a.film-title-name"):
            r = _build_result(link, is_series, seen)
            if r is not None:
                results.append(r)
    return results


def search(client, query):
    url = f"{BASE_URL}/hledat/?q={quote(query)}"
    html = client.get(url, ttl=86400)  # short TTL for searches
    return parse_search(html)
