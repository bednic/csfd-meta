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
