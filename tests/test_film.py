from conftest import load_fixture
from csfd.film import parse_film

URL = "https://www.csfd.cz/film/9499-matrix/"


def film():
    return parse_film(load_fixture("film.html"), URL)


def test_core_text():
    f = film()
    assert f.csfd_id == "9499"
    assert f.title == "Matrix"
    assert isinstance(f.original_title, str) and f.original_title
    assert f.year == 1999
    assert f.runtime == 136
    assert f.plot and len(f.plot) > 20
    assert "Akční" in f.genres
    assert "Sci-Fi" in f.genres


def test_rating_scaled_0_to_10():
    f = film()
    assert f.rating == 9.0  # CSFD shows 90%
    assert 0.0 <= f.rating <= 10.0


def test_cast_and_crew():
    f = film()
    director_names = [p.name for p in f.directors]
    assert any("Wachowski" in n for n in director_names)
    cast_names = [p.name for p in f.cast]
    assert "Keanu Reeves" in cast_names
    # cast must be the "Hrají" group only — directors must not leak into cast
    assert not any("Wachowski" in n for n in cast_names)


def test_artwork_present_and_capped():
    f = film()
    assert any(a.kind == "poster" for a in f.artwork)
    assert len(f.artwork) <= 5


def test_countries():
    assert film().countries == ["USA"]


def test_votes_parsed():
    assert film().votes == 112356
