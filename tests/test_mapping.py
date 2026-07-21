import xbmcgui
from csfd.models import CsfdFilm, Person, Artwork
from kodi.mapping import film_to_listitem


def sample():
    return CsfdFilm(
        csfd_id="9499", url="https://www.csfd.cz/film/9499/", title="Matrix",
        original_title="The Matrix", year=1999, plot="A hacker...",
        runtime=136, countries=["USA"], genres=["Akční", "Sci-Fi"],
        rating=8.6, votes=120000,
        cast=[Person(name="Keanu Reeves", role="Neo")],
        directors=[Person(name="Lana Wachowski")],
        writers=[Person(name="Lilly Wachowski")],
        artwork=[Artwork(url="http://img/p.jpg", kind="poster"),
                 Artwork(url="http://img/f.jpg", kind="fanart")],
    )


def test_maps_core_fields_and_rating():
    li = film_to_listitem(sample(), prefer_original=False)
    tag = li.getVideoInfoTag().data
    assert tag["title"] == "Matrix"
    assert tag["originaltitle"] == "The Matrix"
    assert tag["year"] == 1999
    assert tag["duration"] == 136 * 60
    assert tag["genres"] == ["Akční", "Sci-Fi"]
    assert tag["ratings"][0]["csfd"] == (8.6, 120000)
    assert tag["ratings"][1] == "csfd"
    assert tag["uniqueids"] == ({"csfd": "9499"}, "csfd")


def test_prefer_original_swaps_display_title():
    li = film_to_listitem(sample(), prefer_original=True)
    tag = li.getVideoInfoTag().data
    assert tag["title"] == "The Matrix"
    assert tag["originaltitle"] == "The Matrix"


def test_cast_and_art_mapped():
    li = film_to_listitem(sample(), prefer_original=False)
    tag = li.getVideoInfoTag().data
    assert tag["cast"][0].name == "Keanu Reeves"
    assert tag["cast"][0].role == "Neo"
    assert li.art["poster"] == "http://img/p.jpg"
    assert li.art["fanart"] == "http://img/f.jpg"
