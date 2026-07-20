from csfd.urls import BASE_URL, film_id_from_url, canonical_film_url, absolute_url
from csfd import models


def test_film_id_extracted_from_full_url():
    assert film_id_from_url("https://www.csfd.cz/film/12345-matrix/") == "12345"


def test_film_id_extracted_from_episode_subpage():
    url = "https://www.csfd.cz/film/700-bratrstvo-neohrozenych/1000-epizoda/"
    assert film_id_from_url(url) == "700"


def test_film_id_none_for_non_film_url():
    assert film_id_from_url("https://www.csfd.cz/uzivatel/1-nekdo/") is None


def test_canonical_film_url_strips_slug_and_subpages():
    url = "https://www.csfd.cz/film/12345-matrix/prehled/"
    assert canonical_film_url(url) == "https://www.csfd.cz/film/12345/"


def test_absolute_url_resolves_relative_href():
    assert absolute_url("/film/1-x/") == f"{BASE_URL}/film/1-x/"


def test_absolute_url_passes_through_absolute():
    assert absolute_url("https://www.csfd.cz/film/1-x/") == "https://www.csfd.cz/film/1-x/"


def test_models_construct_with_defaults():
    f = models.CsfdFilm(csfd_id="1", url="u", title="T")
    assert f.genres == [] and f.cast == [] and f.rating is None
