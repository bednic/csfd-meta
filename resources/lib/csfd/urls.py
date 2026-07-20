import re
from urllib.parse import urljoin

BASE_URL = "https://www.csfd.cz"

_FILM_ID_RE = re.compile(r"/film/(\d+)")


def film_id_from_url(url: str) -> "str | None":
    if not url:
        return None
    m = _FILM_ID_RE.search(url)
    return m.group(1) if m else None


def canonical_film_url(url: str) -> str:
    fid = film_id_from_url(url)
    if fid is None:
        return url
    return f"{BASE_URL}/film/{fid}/"


def absolute_url(href: str) -> str:
    if not href:
        return href
    return urljoin(BASE_URL + "/", href)
