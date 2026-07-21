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
