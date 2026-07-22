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


def test_classifies_by_section_not_label():
    # Real capture of https://www.csfd.cz/hledat/?q=tom+a+jerry.
    # Everything under #films is a movie, everything under #series is a series,
    # regardless of the type label text.
    results = parse_search(load_fixture("search_tom_a_jerry.html"))
    by_id = {r.csfd_id: r for r in results}
    # #films
    assert by_id["253143"].is_series is False and by_id["253143"].year == 2021
    assert by_id["71465"].is_series is False and by_id["71465"].year == 1992
    # #series (top-level series only; the "(série)"/"(epizoda)" sub-pages of
    # 69266 are excluded as sub-results)
    assert by_id["69266"].is_series is True and by_id["69266"].year == 1940
    assert by_id["253119"].is_series is True   # Příběhy Toma a Jerryho
    assert by_id["371157"].is_series is True   # Show Toma a Jerryho
    # same title "tom a jerry" appears as both a 2021 film and a 1940 series
    assert by_id["253143"].is_series != by_id["69266"].is_series


def test_excludes_series_episode_and_season_subpages():
    results = parse_search(load_fixture("search_tom_a_jerry.html"))
    # no result is an episode ("busy-buddies") or season/era ("...-era") sub-page
    assert not any(len(r.url.rstrip("/").split("/film/")[1].split("/")) > 2
                   for r in results)
    assert all("-era/" not in r.url and "busy-buddies" not in r.url
               for r in results)


def test_search_series_count_and_movie_count():
    results = parse_search(load_fixture("search_tom_a_jerry.html"))
    assert sum(not r.is_series for r in results) == 7   # #films
    assert sum(r.is_series for r in results) == 3        # top-level #series


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
