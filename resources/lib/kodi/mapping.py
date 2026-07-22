"""Kodi ListItem/InfoTagVideo/Actor construction.

This is the ONLY module allowed to build Kodi ListItem, InfoTagVideo, or
Actor objects. `resources/lib/csfd/` stays Kodi-free; this module maps its
plain dataclasses onto the Kodi Omega InfoTagVideo API.
"""
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


def search_result_to_listitem(result):
    """Directory ListItem for one search candidate.

    Kodi's "choose the right match" dialog shows the ListItem label, so append
    the year — many films/series share a title and only the year tells them
    apart (e.g. Tom a Jerry 1940 seriál vs 2021 film).
    """
    label = result.title or ""
    if result.year:
        label = "%s (%d)" % (label, result.year)
    li = xbmcgui.ListItem(label, offscreen=True)
    tag = li.getVideoInfoTag()
    tag.setUniqueIDs({"csfd": result.csfd_id}, "csfd")
    if result.year:
        tag.setYear(result.year)
    if result.thumb:
        li.setArt({"thumb": result.thumb})
    return li


def nfo_listitem(url):
    """Minimal ListItem carrying a resolved CSFD url for the NfoUrl action."""
    return xbmcgui.ListItem(url, offscreen=True)


def episode_to_listitem(ep):
    """Directory/detail ListItem for one CsfdEpisode."""
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
