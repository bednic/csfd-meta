import logging
import re
from bs4 import BeautifulSoup

from .models import CsfdFilm, Person, Artwork
from .urls import absolute_url, canonical_film_url, film_id_from_url

log = logging.getLogger(__name__)
_INT_RE = re.compile(r"(\d+)")


def _text(node):
    return node.get_text(strip=True) if node else None


def _safe(fn, field):
    """Run an extractor, swallowing/logging any failure (defensive parsing)."""
    try:
        return fn()
    except Exception:
        log.warning("csfd film: failed to parse %s", field)
        return None


def _people(soup, header_words):
    """Extract a creator group whose <h4> label matches any header word."""
    out = []
    for group in soup.select(".creators > div"):
        h4 = group.select_one("h4")
        if not h4:
            continue
        label = h4.get_text(strip=True).lower()
        if not any(w in label for w in header_words):
            continue
        for a in group.select("a[href*='/tvurce/']"):
            name = a.get_text(strip=True)
            if name:
                out.append(Person(name=name))
    return out


def parse_film(html, url, max_art=5):
    soup = BeautifulSoup(html, "html.parser")
    fid = film_id_from_url(url) or ""
    canonical = canonical_film_url(url)

    title = _safe(lambda: _text(soup.select_one(".film-header-name h1")), "title")

    def _orig():
        # film-names lists title variants, each `li` = a flag img + the name.
        # The Czech/Slovak entries are localized titles; the original is the
        # first entry flagged with another country.
        for li in soup.select("ul.film-names li"):
            flag = li.select_one("img.flag")
            country = (flag.get("title", "") if flag else "").strip().lower()
            if country and country not in ("česko", "cesko", "slovensko"):
                txt = li.get_text(strip=True)
                if txt:
                    return txt
        return None
    original_title = _safe(_orig, "original_title")

    def _year():
        node = soup.select_one(".origin")
        m = re.search(r"(\d{4})", node.get_text()) if node else None
        return int(m.group(1)) if m else None
    year = _safe(_year, "year")

    def _plot():
        # Verified: plot lives in `.plot-preview p` (`.plot-full` only appears
        # when the "více" expander is used, which server-render omits).
        return _text(soup.select_one(".plot-full p, .plot-preview p, .plot-full"))
    plot = _safe(_plot, "plot")

    def _genres():
        # Verified: genres are anchor texts inside `.genres` (bullet-separated),
        # NOT a slash-joined string.
        return [a.get_text(strip=True)
                for a in soup.select(".genres a")
                if a.get_text(strip=True)]
    genres = _safe(_genres, "genres") or []

    def _rating():
        node = soup.select_one(".film-rating-average")
        if not node:
            return (None, None)
        m = _INT_RE.search(node.get_text())
        pct = int(m.group(1)) if m else None
        votes_node = soup.select_one(".counter")  # rating count e.g. "(112 356)"
        votes = None
        if votes_node:
            digits = re.sub(r"\D", "", votes_node.get_text())
            votes = int(digits) if digits else None
        return (round(pct / 10.0, 1) if pct is not None else None, votes)
    rating, votes = _safe(_rating, "rating") or (None, None)

    def _runtime():
        node = soup.select_one(".origin")
        if not node:
            return None
        m = re.search(r"(\d+)\s*min", node.get_text())
        return int(m.group(1)) if m else None
    runtime = _safe(_runtime, "runtime")

    def _countries():
        node = soup.select_one(".origin")
        if not node:
            return []
        # countries are the leading text before the first child <span>
        # (origin line = "Country[ / Country] • year • runtime")
        lead = []
        for child in node.children:
            if getattr(child, "name", None) is not None:
                break
            lead.append(str(child))
        text = "".join(lead).strip()
        return [c.strip() for c in text.split("/") if c.strip()]
    countries = _safe(_countries, "countries") or []

    directors = _safe(lambda: _people(soup, ("režie", "rezie", "director")), "directors") or []
    writers = _safe(lambda: _people(soup, ("scénář", "scenar", "writer")), "writers") or []

    # Verified: cast is the "Hrají:" creator group only — NOT every `/tvurce/`
    # link (that would fold in directors, writers, camera, music).
    cast = _safe(lambda: _people(soup, ("hrají", "hraji")), "cast") or []

    def _artwork():
        arts = []
        poster = soup.select_one(".film-posters img")
        if poster:
            src = poster.get("src") or poster.get("data-src")
            if src:
                arts.append(Artwork(url=absolute_url(src), kind="poster"))
        remaining = max(0, max_art - len(arts))
        for img in soup.select(".gallery-item img")[:remaining]:
            src = img.get("src") or img.get("data-src")
            if src:
                arts.append(Artwork(url=absolute_url(src), kind="fanart"))
        return arts[:max_art]
    artwork = _safe(_artwork, "artwork") or []

    is_series = bool(soup.select_one(".film-header .type-serial"))

    return CsfdFilm(
        csfd_id=fid, url=canonical, title=title or "",
        original_title=original_title, year=year, plot=plot,
        runtime=runtime, countries=countries, genres=genres,
        rating=rating, votes=votes, cast=cast, directors=directors,
        writers=writers, artwork=artwork, is_series=is_series,
    )


def film(client, url, max_art=5):
    html = client.get(url)
    return parse_film(html, url, max_art=max_art)
