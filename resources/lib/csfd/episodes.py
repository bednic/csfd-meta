import logging
import re
from bs4 import BeautifulSoup

from .models import CsfdEpisode
from .urls import absolute_url

log = logging.getLogger(__name__)
_SXXEXX_RE = re.compile(r"S(\d+)E(\d+)", re.IGNORECASE)
_ID_SLUG_RE = re.compile(r"/(\d+)-[^/]+")
_SEASON_LINK_RE = re.compile(r"/film/\d+-[^/]+/\d+-serie-\d+/")


def _entity_id(url):
    """The id of the deepest /<digits>-slug/ segment (episode/season id)."""
    ids = _ID_SLUG_RE.findall(url)
    return ids[-1] if ids else None


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
    """Season-page URLs from a series page's .film-episodes-list."""
    soup = BeautifulSoup(html, "html.parser")
    seen, out = set(), []
    for a in soup.select(".film-episodes-list a.film-title-name"):
        href = a.get("href") or ""
        url = absolute_url(href)
        if _SEASON_LINK_RE.search(url) and url not in seen:
            seen.add(url)
            out.append(url)
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
    html = client.get(series_url)
    direct = parse_episode_list(html)
    if direct:
        return direct                      # single-season show: episodes inline
    out = []
    for season_url in parse_season_links(html):
        try:
            out.extend(parse_episode_list(client.get(season_url)))
        except Exception:
            log.warning("csfd episodes: failed season %s", season_url)
    return out
