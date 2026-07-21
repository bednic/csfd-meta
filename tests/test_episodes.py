from conftest import load_fixture
from csfd.episodes import (parse_episode_list, parse_episodes_page,
                          parse_season_links, episodes, _paginated_episodes)


def test_season_page_lists_episodes():
    eps = parse_episode_list(load_fixture("season_episodes.html"))
    assert len(eps) == 10
    first = eps[0]
    assert first.season == 1
    assert first.episode == 1
    assert first.title == "Zima se blíží"
    assert first.csfd_id == "417467"          # episode id, NOT series id 263138
    assert first.url.startswith("https://www.csfd.cz/film/263138-hra-o-truny/417467")


def test_series_page_has_no_direct_episodes():
    # the series page lists SEASONS (no SxxExx), so no episodes parse from it
    assert parse_episode_list(load_fixture("series_episodes.html")) == []


def test_series_page_yields_season_links():
    links = parse_season_links(load_fixture("series_episodes.html"))
    assert len(links) == 8
    assert all("-serie-" in u for u in links)
    assert links[0].startswith("https://www.csfd.cz/film/263138-hra-o-truny/")


def test_named_season_links():
    # seasons with descriptive slugs (era names), not serie-N, must still be found
    links = parse_season_links(load_fixture("series_named_seasons.html"))
    assert len(links) == 3
    assert links[0].endswith("/764673-hanna-barbera-era/prehled/")
    assert all(u.startswith("https://www.csfd.cz/film/69266-tom-a-jerry/")
               for u in links)


def test_epizody_tab_multiseason():
    # /epizody/ lists every season on one page; (SxxExx) rows are episodes,
    # season-header rows (no marker) are skipped.
    eps = parse_episodes_page(load_fixture("epizody_multiseason.html"))
    assert [(e.season, e.episode) for e in eps] == [(1, 1), (1, 2), (2, 1)]
    assert eps[0].csfd_id == "69179"          # episode id, not the series id
    assert eps[0].title == "Jak kočka dostala padáka"


def test_epizody_tab_singleseason():
    # single-season shows use (Exx) with no season number -> season 1
    eps = parse_episodes_page(load_fixture("epizody_singleseason.html"))
    assert [(e.season, e.episode) for e in eps] == [(1, 1), (1, 2), (1, 3)]
    assert eps[0].csfd_id == "683977"


def test_episodes_prefers_epizody_tab():
    page = load_fixture("epizody_multiseason.html")
    fetched = []

    class FakeClient:
        def get(self, url, ttl=None):
            fetched.append(url)
            return page

    eps = episodes(FakeClient(),
                   "https://www.csfd.cz/film/69266-tom-a-jerry/prehled/")
    # one fetch, of the /epizody/ tab; no season-page crawling
    assert fetched == ["https://www.csfd.cz/film/69266-tom-a-jerry/epizody/"]
    assert [(e.season, e.episode) for e in eps] == [(1, 1), (1, 2), (2, 1)]


def test_paginated_season_collects_all_pages():
    # fallback path: a season page paginated via ?seriePage=N
    p1 = load_fixture("season_page_1.html")
    p2 = load_fixture("season_page_2.html")

    class FakeClient:
        def get(self, url, ttl=None):
            return p2 if "seriePage=2" in url else p1

    eps = _paginated_episodes(
        FakeClient(),
        "https://www.csfd.cz/film/69266-tom-a-jerry/764673-hanna-barbera-era/prehled/")
    assert [(e.season, e.episode) for e in eps] == [(1, 1), (1, 2), (1, 3), (1, 4)]


def test_episodes_falls_back_to_season_crawl():
    # when /epizody/ yields nothing, fall back to series-page + season sub-pages
    series_html = load_fixture("series_episodes.html")
    season_html = load_fixture("season_episodes.html")

    class FakeClient:
        def get(self, url, ttl=None):
            if url.endswith("/epizody/"):
                return series_html        # no episode markers -> triggers fallback
            return season_html if "-serie-" in url else series_html

    eps = episodes(FakeClient(), "https://www.csfd.cz/film/263138-hra-o-truny/prehled/")
    # 8 seasons, each FakeClient returns the same 10-episode season page
    assert len(eps) == 8 * 10
    assert all(e.csfd_id.isdigit() for e in eps)
    assert all(e.title for e in eps)
