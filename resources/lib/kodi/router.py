import logging
from urllib.parse import parse_qs

from .movie_scraper import movie_find, movie_details, nfo_url
from .tv_scraper import tv_find, tv_details, episode_list, episode_details

log = logging.getLogger(__name__)


def parse_argv(argv):
    handle = int(argv[1]) if len(argv) > 1 and argv[1].lstrip("-").isdigit() else -1
    query = ""
    for a in argv:
        if a.startswith("?") or "action=" in a:
            query = a.lstrip("?")
            break
    params = {k: v[0] for k, v in parse_qs(query).items()}
    return handle, params


_MOVIE = {
    "find": movie_find,
    "getdetails": movie_details,
    "NfoUrl": nfo_url,
}
_TV = {
    "find": tv_find,
    "getdetails": tv_details,
    "getepisodelist": episode_list,
    "getepisodedetails": episode_details,
    "NfoUrl": nfo_url,
}


def _dispatch(table, handle, action, params):
    handler = table.get(action)
    if handler is None:
        log.warning("csfd: unknown action %r", action)
        return
    try:
        handler(handle, params)
    except Exception:
        log.exception("csfd: action %r failed", action)


def route_movie(handle, action, params):
    _dispatch(_MOVIE, handle, action, params)


def route_tv(handle, action, params):
    _dispatch(_TV, handle, action, params)
