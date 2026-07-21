import logging

log = logging.getLogger(__name__)

# Imported lazily so the router module can be unit-tested and so that
# missing handlers during early bring-up don't break import.
from .movie_scraper import movie_find, movie_details, nfo_url          # noqa: E402
from .tv_scraper import (                                              # noqa: E402
    tv_find, tv_details, episode_list, episode_details,
)

def _details(handle, params):
    if (params.get("mediatype") == "tvshow"
            or params.get("content") == "tvshows"):
        return tv_details(handle, params)
    return movie_details(handle, params)


_DISPATCH = {
    "find": lambda h, p: movie_find(h, p),
    "getdetails": _details,
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
