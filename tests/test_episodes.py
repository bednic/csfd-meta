from conftest import load_fixture
from csfd.episodes import parse_episode_list, parse_season_links, episodes


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


def test_episodes_orchestrates_series_then_seasons():
    series_html = load_fixture("series_episodes.html")
    season_html = load_fixture("season_episodes.html")

    class FakeClient:
        def get(self, url, ttl=None):
            return season_html if "-serie-" in url else series_html

    eps = episodes(FakeClient(), "https://www.csfd.cz/film/263138-hra-o-truny/")
    # 8 seasons, each FakeClient returns the same 10-episode season page
    assert len(eps) == 8 * 10
    assert all(e.csfd_id.isdigit() for e in eps)
    assert all(e.title for e in eps)
