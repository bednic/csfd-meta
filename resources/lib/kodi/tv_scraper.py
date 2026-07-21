import logging

import xbmcplugin

from csfd import episodes as csfd_episodes
from csfd import film as csfd_film
from .mapping import film_to_listitem, episode_to_listitem
from .movie_scraper import build_client
from .settings import Settings

log = logging.getLogger(__name__)


def tv_find(handle, params):
    from .movie_scraper import _find
    _find(handle, params, lambda r: r.is_series)


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
        li = episode_to_listitem(ep)
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
    episode_id = csfd_episodes._entity_id(url) or f.csfd_id
    ep = CsfdEpisode(csfd_id=episode_id, url=f.url, title=f.title or "",
                     season=season, episode=number, plot=f.plot)
    li = episode_to_listitem(ep)
    xbmcplugin.setResolvedUrl(handle, True, li)
