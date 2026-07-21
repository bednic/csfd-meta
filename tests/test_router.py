import xbmcplugin
from kodi.router import route_movie, route_tv, parse_argv


def test_parse_argv_extracts_handle_and_params():
    handle, params = parse_argv(["addon_movie.py", "5", "?action=find&title=Matrix"])
    assert handle == 5
    assert params == {"action": "find", "title": "Matrix"}


def test_unknown_action_is_noop():
    route_movie(1, "bogus", {})
    route_tv(1, "bogus", {})


def test_route_movie_find_dispatches(monkeypatch):
    import kodi.router as r
    called = {}
    monkeypatch.setitem(r._MOVIE, "find", lambda h, p: called.setdefault("m", p))
    route_movie(1, "find", {"title": "X"})
    assert called["m"] == {"title": "X"}


def test_route_tv_getepisodelist_dispatches(monkeypatch):
    import kodi.router as r
    called = {}
    monkeypatch.setitem(r._TV, "getepisodelist", lambda h, p: called.setdefault("t", p))
    route_tv(1, "getepisodelist", {"url": "u"})
    assert called["t"] == {"url": "u"}
