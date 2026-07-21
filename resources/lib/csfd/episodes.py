import logging
import re
from bs4 import BeautifulSoup

from .models import CsfdEpisode
from .urls import absolute_url

log = logging.getLogger(__name__)
_SXXEXX_RE = re.compile(r"S(\d+)E(\d+)", re.IGNORECASE)
# Episode marker on the /epizody/ tab: (SxxExx) for multi-season shows, (Exx)
# for single-season shows (which then belong to season 1).
_EPISODE_MARKER_RE = re.compile(r"(?:S(\d+))?E(\d+)", re.IGNORECASE)
_ID_SLUG_RE = re.compile(r"/(\d+)-[^/]+")
_FILM_BASE_RE = re.compile(r"(/film/\d+-[^/]+/)")
# A season sub-page is a second /<id>-slug/ segment under the film. The slug is
# usually serie-<n> but CSFD also uses descriptive names (hanna-barbera-era),
# so match on the shape, not the slug text.
_SEASON_LINK_RE = re.compile(r"/film/\d+-[^/]+/\d+-[^/]+/")


def _entity_id(url):
    """The id of the deepest /<digits>-slug/ segment (episode/season id)."""
    ids = _ID_SLUG_RE.findall(url)
    return ids[-1] if ids else None


def _episodes_url(series_url):
    """The /epizody/ tab URL for a film, derived from any of its page URLs."""
    m = _FILM_BASE_RE.search(series_url)
    if not m:
        return series_url
    return absolute_url(m.group(1) + "epizody/")


def parse_episodes_page(html):
    """Every episode from a film's /epizody/ tab (single page, no pagination).

    The tab lists all seasons in document order. Episode rows carry a marker:
    (SxxExx) for multi-season shows, (Exx) for single-season shows (season 1).
    Season-header rows carry no marker and are skipped.
    """
    soup = BeautifulSoup(html, "html.parser")
    scope = soup.select_one(".movie-profile--tab-episodes") or soup
    out = []
    for h in scope.select("h3.film-title-inline"):
        a = h.select_one("a.film-title-name")
        if not a or not a.get("href"):
            continue
        info = h.select_one(".film-title-info")
        m = _EPISODE_MARKER_RE.search(info.get_text()) if info else None
        if not m:
            continue  # a season header, not an episode
        url = absolute_url(a["href"])
        eid = _entity_id(url)
        if not eid:
            continue
        out.append(CsfdEpisode(
            csfd_id=eid, url=url, title=a.get_text(strip=True),
            season=int(m.group(1)) if m.group(1) else 1,
            episode=int(m.group(2))))
    return _dedup(out)


def parse_episode_list(html):
    """Episodes from a page whose .film-episodes-list rows carry (SxxExx)."""
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for li in soup.select(".film-episodes-list li"):
        a = li.select_one("a.film-title-name")
        if not a or not a.get("href"):
            continue
        info = li.select_one(".film-title-info .info") or li.select_one(".info")
        m = _SXXEXX_RE.search(info.get_text()) if info else None
        if not m:
            continue  # a season row (no SxxExx), not an episode
        url = absolute_url(a["href"])
        eid = _entity_id(url)
        if not eid:
            continue
        out.append(CsfdEpisode(
            csfd_id=eid, url=url, title=a.get_text(strip=True),
            season=int(m.group(1)), episode=int(m.group(2))))
    return _dedup(out)


def parse_season_links(html):
    """Season-page URLs from a series page's .film-episodes-list.

    A season row links to a film sub-page and, unlike an episode row, carries
    no (SxxExx) marker; skip anything that looks like an episode so this stays
    correct even if handed a season page.
    """
    soup = BeautifulSoup(html, "html.parser")
    seen, out = set(), []
    for li in soup.select(".film-episodes-list li"):
        a = li.select_one("a.film-title-name")
        if not a or not a.get("href"):
            continue
        info = li.select_one(".film-title-info .info") or li.select_one(".info")
        if info and _SXXEXX_RE.search(info.get_text()):
            continue  # an episode row, not a season
        url = absolute_url(a["href"])
        if _SEASON_LINK_RE.search(url) and url not in seen:
            seen.add(url)
            out.append(url)
    return out


def _next_page_url(html):
    """The ?seriePage=N 'next' link on a season page, or None on the last page."""
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.select("a.page-next"):
        if "disabled" in (a.get("class") or []):
            continue
        href = a.get("href") or ""
        if "seriePage=" in href:
            return absolute_url(href)
    return None


def _paginated_episodes(client, url):
    """All episodes across a season page's ?seriePage pagination."""
    out, seen = [], set()
    while url and url not in seen:
        seen.add(url)
        html = client.get(url)
        out.extend(parse_episode_list(html))
        url = _next_page_url(html)
    return out


def _dedup(eps):
    seen, out = set(), []
    for e in eps:
        key = (e.season, e.episode)
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    return out


def episodes(client, series_url):
    # Primary: the /epizody/ tab lists every season's episodes on one page.
    eps = parse_episodes_page(client.get(_episodes_url(series_url)))
    if eps:
        return eps
    # Fallback: parse the series page directly. A single-season show lists its
    # episodes inline; a multi-season show lists per-season sub-pages, each of
    # which may be paginated.
    html = client.get(series_url)
    if parse_episode_list(html):
        return _paginated_episodes(client, series_url)
    out = []
    for season_url in parse_season_links(html):
        try:
            out.extend(_paginated_episodes(client, season_url))
        except Exception:
            log.warning("csfd episodes: failed season %s", season_url)
    return out
