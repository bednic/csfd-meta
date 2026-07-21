from conftest import load_fixture
from csfd.search import parse_search


def test_parse_search_returns_results():
    results = parse_search(load_fixture("search.html"))
    assert len(results) >= 1


def test_first_result_has_core_fields():
    r = parse_search(load_fixture("search.html"))[0]
    assert r.csfd_id.isdigit()
    assert r.url.startswith("https://www.csfd.cz/film/")
    assert r.title  # non-empty
    # Adjust the next two to the actual first result in your captured fixture:
    assert "Matrix" in r.title
    assert r.year == 1999


def test_series_flagged():
    results = parse_search(load_fixture("search.html"))
    assert all(isinstance(r.is_series, bool) for r in results)


def test_excludes_episode_subresults_and_keeps_distinct_films():
    results = parse_search(load_fixture("search.html"))
    ids = [r.csfd_id for r in results]
    # no duplicate ids
    assert len(ids) == len(set(ids))
    # the Matrix trilogy top-level films are all present and distinct
    assert {"9499", "9497", "9498"} <= set(ids)
    # no result is an episode/season sub-page URL
    import re as _re
    assert all(len(_re.findall(r"/\d+-[^/]+", r.url)) == 1 for r in results)
