import xbmcplugin
from kodi.router import route


def test_unknown_action_does_not_raise():
    xbmcplugin.reset()
    route(1, "bogus", {})  # should be a no-op, not an exception


def test_find_action_dispatches(monkeypatch):
    called = {}
    import kodi.router as r
    monkeypatch.setattr(r, "movie_find",
                        lambda handle, params: called.setdefault("find", params))
    route(1, "find", {"title": "Matrix", "year": "1999"})
    assert called["find"] == {"title": "Matrix", "year": "1999"}
