import xbmcplugin
from csfd.models import SearchResult
from kodi import movie_scraper


def test_movie_find_excludes_series(monkeypatch):
    xbmcplugin.reset()
    results = [
        SearchResult(csfd_id="1", url="https://www.csfd.cz/film/1-a/",
                     title="A film", year=1999, is_series=False),
        SearchResult(csfd_id="2", url="https://www.csfd.cz/film/2-b/",
                     title="B series", year=2000, is_series=True),
    ]
    monkeypatch.setattr(movie_scraper.csfd_search, "search",
                        lambda client, query: results)
    movie_scraper.movie_find(1, {"title": "x"})
    urls = [u for (_h, u, _li, _f) in xbmcplugin._added]
    assert "https://www.csfd.cz/film/1-a/" in urls
    assert "https://www.csfd.cz/film/2-b/" not in urls


def test_tv_find_includes_only_series(monkeypatch):
    from kodi import tv_scraper
    xbmcplugin.reset()
    results = [
        SearchResult(csfd_id="1", url="https://www.csfd.cz/film/1-a/",
                     title="A film", year=1999, is_series=False),
        SearchResult(csfd_id="2", url="https://www.csfd.cz/film/2-b/",
                     title="B series", year=2000, is_series=True),
    ]
    monkeypatch.setattr(movie_scraper.csfd_search, "search",
                        lambda client, query: results)
    tv_scraper.tv_find(1, {"title": "x"})
    urls = [u for (_h, u, _li, _f) in xbmcplugin._added]
    assert "https://www.csfd.cz/film/2-b/" in urls
    assert "https://www.csfd.cz/film/1-a/" not in urls
