import os
import pytest

pytestmark = pytest.mark.network

RELAY_URL = os.environ.get("CSFD_RELAY_URL", "http://nas:9753")


@pytest.fixture(scope="module")
def client():
    from csfd.client import CsfdClient
    return CsfdClient(RELAY_URL, cache_dir=None)


def test_search_live(client):
    from csfd.search import search
    results = search(client, "Matrix")
    assert len(results) >= 1
    assert results[0].csfd_id.isdigit()


def test_film_live(client):
    from csfd.film import film
    f = film(client, "https://www.csfd.cz/film/9499-matrix/")
    assert f.title
    assert f.rating is not None
    assert len(f.directors) >= 1
    assert len(f.cast) >= 1
    assert any(a.kind == "poster" for a in f.artwork)
